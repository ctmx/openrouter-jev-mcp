import json
import multiprocessing
import fcntl
import os
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from pathlib import Path

from src.diagnostics import DiagnosticLogger, validate_exclusions
from src.gateway import JevGateway
import httpx


def _write_from_process(directory: str, count: int, cap: int = 500) -> None:
    logger = DiagnosticLogger(Path(directory), max_total_bytes=cap, max_record_bytes=100)
    for number in range(count):
        logger.record("process", state="x" * 1_000, metadata={"number": number})
    logger.close()


def _paused_write_from_process(directory: str, entered, release) -> None:
    logger = DiagnosticLogger(Path(directory), max_total_bytes=120, max_record_bytes=100)
    original = os.write
    def paused(fd, data):
        entered.set()
        release.wait(3)
        return original(fd, data)
    with patch("src.diagnostics.os.write", paused):
        logger.record("first", state="x" * 1_000)
    logger.close()


class DiagnosticLoggerTests(unittest.TestCase):
    def test_record_filters_nested_secrets_and_excluded_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            logger = DiagnosticLogger(Path(directory), known_secrets=("sentinel-key",))
            state = {"token": "sentinel-key", "nested": {"keep": "value", "private": "do-not-log"}}
            logger.record(
                "judgement",
                state=state,
                answers={"answer": "Bearer sentinel-key"},
                metadata={"authorization": "Bearer sentinel-key", "request_id": "safe"},
                exclusions=["/state/nested/private"],
            )
            logger.close()

            records = list(Path(directory).glob("*.jsonl"))
            self.assertEqual(1, len(records))
            contents = records[0].read_text(encoding="utf-8")
            record = json.loads(contents)
            self.assertEqual("judgement", record["event"])
            self.assertEqual("value", record["state"]["nested"]["keep"])
            self.assertNotIn("private", record["state"]["nested"])
            self.assertNotIn("sentinel-key", contents)
            self.assertNotIn("authorization", record["metadata"])
            self.assertEqual("do-not-log", state["nested"]["private"])

    def test_exclusions_are_full_record_json_pointers(self) -> None:
        self.assertEqual((("state", "a/b", "~key"),), validate_exclusions(["/state/a~1b/~0key"]))
        for invalid in ("state/value", "/request/value", "/state/bad~2escape"):
            with self.assertRaises(ValueError):
                validate_exclusions([invalid])
        for invalid in (float("nan"), float("inf"), 0):
            with self.assertRaises(ValueError):
                DiagnosticLogger(lock_timeout_seconds=invalid)

    def test_old_records_are_removed_before_a_new_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            old = Path(directory) / "record-old.jsonl"
            old.write_text("{}\n", encoding="utf-8")
            os.utime(old, (0, 0))
            logger = DiagnosticLogger(Path(directory), clock=lambda: 100, retention_seconds=10)
            logger.record("judgement", state="safe")
            self.assertFalse(old.exists())
            logger.close()

    def test_startup_removes_stale_records_before_any_judgement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            old = Path(directory) / "record-stale.jsonl"
            old.write_text("{}\n", encoding="utf-8")
            os.utime(old, (0, 0))
            logger = DiagnosticLogger(Path(directory), clock=lambda: 100, retention_seconds=10)
            logger.start()
            self.assertFalse(old.exists())
            logger.close()

    def test_record_is_bounded_and_marks_truncation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            logger = DiagnosticLogger(Path(directory), max_record_bytes=128)
            logger.record("judgement", state="x" * 10_000)
            logger.close()
            content = next(Path(directory).glob("*.jsonl")).read_bytes()
            self.assertLessEqual(len(content), 129)
            self.assertTrue(json.loads(content)["truncated"])

    def test_unsafe_symlink_directory_only_warns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target"
            target.mkdir()
            unsafe = root / "unsafe"
            unsafe.symlink_to(target, target_is_directory=True)
            logger = DiagnosticLogger(unsafe)
            logger.record("judgement", state="safe")
            self.assertEqual([], list(target.glob("*.jsonl")))
            logger.close()

    def test_simultaneous_loggers_keep_json_lines_and_private_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            loggers = [DiagnosticLogger(Path(directory)) for _ in range(4)]
            threads = [threading.Thread(target=lambda logger=logger: logger.record("judgement", state={"worker": 1}))
                       for logger in loggers]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            for logger in loggers:
                logger.close()
            paths = list(Path(directory).glob("record-*.jsonl"))
            self.assertTrue(all(path.stat().st_mode & 0o777 == 0o600 for path in paths))
            self.assertEqual(4, len(paths))

    def test_total_byte_cap_rotates_the_active_record_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            logger = DiagnosticLogger(Path(directory), max_total_bytes=120, max_record_bytes=100)
            logger.record("first", state="x" * 1_000)
            logger.record("second", state="y" * 1_000)
            logger.close()
            path = next(Path(directory).glob("*.jsonl"))
            self.assertLessEqual(path.stat().st_size, 120)
            self.assertEqual("second", json.loads(path.read_text(encoding="utf-8"))["event"])

    def test_cap_evicts_every_required_old_segment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            logger = DiagnosticLogger(Path(directory), max_total_bytes=120, max_record_bytes=100)
            for event in ("one", "two", "three", "four"):
                logger.record(event, state="x" * 1_000)
            logger.close()
            records = list(Path(directory).glob("record-*.jsonl"))
            self.assertEqual(1, len(records))
            self.assertEqual("four", json.loads(records[0].read_text())["event"])

    def test_hardlinked_segment_is_not_unlinked_or_counted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            external = root / "external"
            external.write_text("outside", encoding="utf-8")
            hardlinked = root / "record-unsafe.jsonl"
            os.link(external, hardlinked)
            logger = DiagnosticLogger(root, max_total_bytes=120, max_record_bytes=100)
            logger.record("safe", state="x" * 1_000)
            logger.close()
            self.assertTrue(external.exists())
            self.assertEqual("outside", external.read_text(encoding="utf-8"))

    def test_process_writers_keep_the_aggregate_cap(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workers = [multiprocessing.Process(target=_write_from_process, args=(directory, 4)) for _ in range(3)]
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join(5)
                self.assertEqual(0, worker.exitcode)
            total = sum(path.stat().st_size for path in Path(directory).glob("record-*.jsonl"))
            self.assertLessEqual(total, 500)

    def test_interleaved_process_writers_preserve_cap_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            entered, release = multiprocessing.Event(), multiprocessing.Event()
            first = multiprocessing.Process(target=_paused_write_from_process, args=(directory, entered, release))
            first.start()
            self.assertTrue(entered.wait(3))
            second = multiprocessing.Process(target=_write_from_process, args=(directory, 1, 120))
            second.start()
            time.sleep(0.05)
            self.assertTrue(second.is_alive())
            release.set()
            first.join(5)
            second.join(5)
            self.assertEqual(0, first.exitcode)
            self.assertEqual(0, second.exitcode)
            total = sum(path.stat().st_size for path in Path(directory).glob("record-*.jsonl"))
            self.assertLessEqual(total, 120)

    def test_lock_contention_returns_without_blocking_a_caller(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock = root / ".lock"
            with lock.open("wb") as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                logger = DiagnosticLogger(root, lock_timeout_seconds=0.02)
                started = time.monotonic()
                logger.record("judgement", state="safe")
                self.assertLess(time.monotonic() - started, 0.2)
                logger.close()

    def test_lock_timeouts_do_not_leak_file_descriptors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (root / ".lock").open("wb") as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                before = len(list(Path("/proc/self/fd").iterdir()))
                for _ in range(20):
                    DiagnosticLogger(root, lock_timeout_seconds=0.001).record("judgement", state="safe")
                self.assertLessEqual(len(list(Path("/proc/self/fd").iterdir())), before + 1)

    def test_short_write_is_completed_or_no_invalid_record_remains(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            logger = DiagnosticLogger(Path(directory))
            real_write, calls = os.write, [0]
            def short_write(fd, data):
                calls[0] += 1
                return real_write(fd, data[: max(1, len(data) // 2)])
            with patch("src.diagnostics.os.write", short_write):
                logger.record("judgement", state="safe")
            logger.close()
            records = list(Path(directory).glob("record-*.jsonl"))
            self.assertEqual(1, len(records))
            self.assertGreater(calls[0], 1)
            json.loads(records[0].read_text())

    def test_injected_logger_filters_arbitrary_configured_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            secret = "arbitrary-provider-key-without-pattern"
            logger = DiagnosticLogger(Path(directory))
            def response(_: httpx.Request) -> httpx.Response:
                return httpx.Response(200, json={"model": "m", "answers": {"check": {"type": "noul", "noul": 0.5}}, "usage": {"echo": secret}})
            gateway = JevGateway(openrouter_api_key=secret, http_transport=httpx.MockTransport(response), logger=logger)
            gateway.check({"key": secret}, "Is this safe?")
            gateway.close()
            contents = "".join(path.read_text() for path in Path(directory).glob("record-*.jsonl"))
            self.assertNotIn(secret, contents)

    def test_secret_keys_and_adjacent_list_exclusions_do_not_leak(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            logger = DiagnosticLogger(Path(directory), known_secrets=("sentinel-key",))
            logger.record("judgement", state={"sentinel-key": "value", "items": ["one", "two", "three"]},
                          exclusions=["/state/items/0", "/state/items/1"])
            logger.close()
            record = json.loads(next(Path(directory).glob("record-*.jsonl")).read_text())
            self.assertNotIn("sentinel-key", json.dumps(record))
            self.assertEqual(["[EXCLUDED]", "[EXCLUDED]", "three"], record["state"]["items"])

    def test_continually_used_log_removes_expired_segments(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            now = [100]
            logger = DiagnosticLogger(Path(directory), retention_seconds=10, clock=lambda: now[0])
            logger.record("old", state="safe")
            old = next(Path(directory).glob("record-*.jsonl"))
            os.utime(old, (0, 0))
            now[0] = 100
            logger.record("new", state="safe")
            logger.close()
            records = [json.loads(path.read_text())["event"] for path in Path(directory).glob("record-*.jsonl")]
            self.assertEqual(["new"], records)
