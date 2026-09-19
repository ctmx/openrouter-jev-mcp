"""Bounded end-to-end tests for the Jev stdio MCP server."""
from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
import tempfile
import unittest
from contextlib import suppress
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "tests" / "stdio_fake_server.py"
DEADLINE_SECONDS = 5
STARTUP_DEADLINE_SECONDS = 15


class _StdioMcp:
    """Minimal JSON-lines MCP client with bounded reads and unconditional cleanup."""

    def __init__(self, log_dir: Path) -> None:
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(ROOT),
            "OPENROUTER_API_KEY": "synthetic-stdio-key",
            "JEV_LOG_DIR": str(log_dir),
        }
        self.process = subprocess.Popen(
            [sys.executable, "-u", str(LAUNCHER)],
            cwd=ROOT,
            env=environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        assert self.process.stdin is not None
        assert self.process.stdout is not None
        self.stdin = self.process.stdin
        self.stdout = self.process.stdout
        self.lines: queue.Queue[str | None] = queue.Queue()
        self.stderr_output = ""
        self.reader = threading.Thread(target=self._read_stdout, daemon=True)
        self.reader.start()
        self.request_id = 0

    def _read_stdout(self) -> None:
        for line in self.stdout:
            self.lines.put(line.decode("utf-8"))
        self.lines.put(None)

    def request(self, method: str, params: dict[str, Any] | None = None, *, startup: bool = False) -> dict[str, Any]:
        self.request_id += 1
        request_id = self.request_id
        message = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            message["params"] = params
        self.stdin.write((json.dumps(message) + "\n").encode("utf-8"))
        deadline = STARTUP_DEADLINE_SECONDS if startup else DEADLINE_SECONDS
        end = time.monotonic() + deadline
        while remaining := end - time.monotonic():
            try:
                line = self.lines.get(timeout=remaining)
            except queue.Empty:
                break
            if line is None:
                break
            # Every stdout line must be a protocol message; logging belongs on stderr.
            response = json.loads(line)
            if response.get("id") == request_id:
                return response
        # Do not read stderr here: a live pipe blocks until process shutdown and
        # was the source of the previous test-suite hang.
        raise AssertionError(f"no response to {method!r} within {deadline}s")

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        message: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        self.stdin.write((json.dumps(message) + "\n").encode("utf-8"))

    def close(self) -> None:
        if self.process.poll() is None:
            # Exit the child before closing streams: the reader can otherwise
            # be blocked inside a pipe read while its file object is closed.
            self.process.terminate()
            try:
                self.process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=1)
        for stream in (self.stdin, self.stdout, self.process.stderr):
            if stream is self.process.stderr:
                with suppress(OSError, ValueError):
                    self.stderr_output = stream.read(8192).decode("utf-8", "replace")
            with suppress(OSError, ValueError):
                stream.close()
        self.reader.join(timeout=1)


def _tool_data(response: dict[str, Any]) -> dict[str, Any]:
    result = response.get("result", {})
    if "structuredContent" in result:
        return result["structuredContent"]
    content = result.get("content", [])
    if content and content[0].get("type") == "text":
        try:
            return json.loads(content[0]["text"])
        except json.JSONDecodeError:
            # MCP may surface an internal tool failure as plain error text.
            return {"_plain_error": content[0]["text"]}
    return result


class StdioMcpTests(unittest.TestCase):
    def _start_mcp(self, log_dir: Path) -> _StdioMcp:
        mcp = _StdioMcp(log_dir)
        initialised = mcp.request("initialize", {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "jev-stdio-test", "version": "1"},
        }, startup=True)
        self.assertIn("result", initialised)
        mcp.notify("notifications/initialized")
        return mcp

    def setUp(self) -> None:
        self.logs = tempfile.TemporaryDirectory()
        self.addCleanup(self.logs.cleanup)
        self.log_dir = Path(self.logs.name)
        self.mcp = self._start_mcp(self.log_dir)
        self.addCleanup(self.mcp.close)

    def call_tool(self, name: str, arguments: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        response = self.mcp.request("tools/call", {"name": name, "arguments": arguments})
        return response, _tool_data(response)

    def test_discovery_and_successful_structured_calls(self) -> None:
        listed = self.mcp.request("tools/list")
        tools = {tool["name"] for tool in listed["result"]["tools"]}
        self.assertEqual({"jev_check", "jev_classify", "jev_score", "jev_evaluate", "jev_health"}, tools)

        _, check = self.call_tool("jev_check", {"state": {"incident": True}, "proposition": "Is there an incident?"})
        self.assertIn("type", check, check)
        self.assertEqual("noul", check["type"])
        self.assertEqual(0.75, check["noul"])

        _, choice = self.call_tool("jev_classify", {
            "state": ["payment", "failed"], "question": "Who owns this?",
            "options": {"billing": "Payment issue", "technical": "Technical issue"},
        })
        self.assertEqual("billing", choice["choice"])

        _, score = self.call_tool("jev_score", {
            "state": "small impact", "question": "How severe?", "levels": ["low", "high"],
        })
        self.assertEqual("score", score["type"])

        _, evaluated = self.call_tool("jev_evaluate", {
            "state": {"payment": "failed"},
            "questions": {
                "urgent": {"type": "noul", "instructions": "Is it urgent?"},
                "owner": {"type": "choice", "instructions": "Who owns it?", "criteria": {"billing": "Payments", "technical": "Bugs"}},
                "severity": {"type": "score", "instructions": "How severe?", "criteria": ["low", "high"]},
            },
        })
        self.assertEqual({"urgent", "owner", "severity"}, set(evaluated["answers"]))

    def test_protocol_errors_and_truthful_health(self) -> None:
        invalid_response, invalid = self.call_tool("jev_check", {"state": "x", "proposition": ""})
        self.assertTrue(invalid_response.get("result", {}).get("isError") or "error" in invalid)

        provider_response, provider = self.call_tool("jev_check", {
            "state": "provider-error", "proposition": "Is this available?",
        })
        self.assertTrue(provider_response.get("result", {}).get("isError") or "error" in provider)

        _, local = self.call_tool("jev_health", {"verify": False})
        self.assertTrue(local["ready"])
        self.assertIn("unverified", str(local).lower())

        _, verified = self.call_tool("jev_health", {"verify": True})
        self.assertIn("ready", verified, verified)
        self.assertTrue(verified["ready"])
        self.assertIn("verified", str(verified).lower())

    def test_retry_and_timeout_are_bounded_protocol_results(self) -> None:
        _, retried = self.call_tool("jev_check", {
            "state": "retry-once", "proposition": "Did the transient request recover?",
        })
        self.assertEqual(0.75, retried["noul"])

        timed_out_response, timed_out = self.call_tool("jev_check", {
            "state": "timeout", "proposition": "Will this time out?",
        })
        self.assertTrue(timed_out_response.get("result", {}).get("isError") or "error" in timed_out)
        if "error" in timed_out:
            self.assertEqual("timeout", timed_out["error"]["category"])

    def test_logging_exclusions_do_not_change_state_and_invalid_pointers_fail(self) -> None:
        state = {"secret": "SENTINEL-private-value", "retained": "ordinary value"}
        _, result = self.call_tool("jev_check", {
            "state": state,
            "proposition": "Does the submitted state contain the sentinel?",
            "logging_exclusions": ["/state/secret"],
        })
        self.assertEqual(0.9, result["noul"])
        records = list(self.log_dir.glob("record-*.jsonl"))
        self.assertTrue(records)
        logged = "\n".join(path.read_text() for path in records)
        self.assertNotIn("SENTINEL-private-value", logged)
        self.assertIn("ordinary value", logged)

        record_count = len(list(self.log_dir.glob("record-*.jsonl")))
        response, invalid = self.call_tool("jev_check", {
            "state": state,
            "proposition": "This must not be judged.",
            "logging_exclusions": ["state/secret"],
        })
        self.assertTrue(response.get("result", {}).get("isError") or "error" in invalid)
        if "error" in invalid:
            self.assertEqual("input_validation", invalid["error"]["category"])
        self.assertEqual(record_count, len(list(self.log_dir.glob("record-*.jsonl"))))

    def test_log_failure_keeps_judgement_and_warns_on_stderr(self) -> None:
        bad_log_path = self.log_dir / "not-a-directory"
        bad_log_path.write_text("file prevents diagnostic directory creation")
        failing = self._start_mcp(bad_log_path)
        self.addCleanup(failing.close)
        response = failing.request("tools/call", {"name": "jev_check", "arguments": {
            "state": "available despite logging failure", "proposition": "Can this succeed?",
        }})
        self.assertEqual(0.75, _tool_data(response)["noul"])
        failing.close()
        self.assertIn("jev diagnostic logging unavailable", failing.stderr_output)

    def test_startup_removes_stale_diagnostic_segment_before_health(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log_dir = Path(directory)
            stale = log_dir / "record-stale.jsonl"
            stale.write_text('{"event":"stale"}\n')
            old = time.time() - 86_401
            os.utime(stale, (old, old))
            child = self._start_mcp(log_dir)
            self.addCleanup(child.close)
            response = child.request("tools/call", {"name": "jev_health", "arguments": {"verify": False}})
            self.assertTrue(_tool_data(response)["ready"])
            self.assertFalse(stale.exists())


if __name__ == "__main__":
    unittest.main()
