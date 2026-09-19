"""Best-effort, private and bounded diagnostic records."""
from __future__ import annotations

import copy
import fcntl
import json
import math
import os
import re
import stat
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

DEFAULT_RETENTION_SECONDS = 86_400
DEFAULT_MAX_TOTAL_BYTES = 20 * 1024 * 1024
DEFAULT_MAX_RECORD_BYTES = 64 * 1024
DEFAULT_MAX_SEGMENTS = 1_024
_SENSITIVE_KEY = re.compile(r"(?:authorization|api[_-]?key|token|secret|password|credential|cookie)", re.I)
_CREDENTIAL = re.compile(r"(?:bearer\s+\S+|sk-[A-Za-z0-9_-]{8,}|sk-or-v1-[A-Za-z0-9_-]{8,})", re.I)


def validate_exclusions(exclusions: Sequence[str] | None) -> tuple[tuple[str, ...], ...]:
    """Validate logging-only RFC 6901 pointers rooted at state, answers or metadata."""
    if exclusions is None:
        return ()
    if not isinstance(exclusions, list) or any(not isinstance(item, str) for item in exclusions):
        raise ValueError("logging_exclusions must be a list of JSON Pointer strings.")
    result = []
    for pointer in exclusions:
        if not pointer.startswith("/"):
            raise ValueError("logging exclusion paths must start with '/'.")
        parts = []
        for raw in pointer[1:].split("/"):
            index = 0
            while index < len(raw):
                if raw[index] == "~":
                    if index + 1 == len(raw) or raw[index + 1] not in "01":
                        raise ValueError("logging exclusion has an invalid JSON Pointer escape.")
                    index += 2
                else:
                    index += 1
            parts.append(raw.replace("~1", "/").replace("~0", "~"))
        if parts[0] not in {"state", "answers", "metadata"}:
            raise ValueError("logging exclusions must target /state, /answers, or /metadata.")
        result.append(tuple(parts))
    return tuple(result)


class DiagnosticLogger:
    """Writes immutable JSON records; all persistence failures are reduced to one stderr warning."""
    def __init__(self, log_dir: str | Path | None = None, *, known_secrets: Iterable[str | None] = (),
                 retention_seconds: int = DEFAULT_RETENTION_SECONDS,
                 max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
                 max_record_bytes: int = DEFAULT_MAX_RECORD_BYTES,
                 max_segments: int = DEFAULT_MAX_SEGMENTS,
                 clock: Callable[[], float] = time.time, cleanup_interval_seconds: int = 60,
                 lock_timeout_seconds: float = 0.1) -> None:
        self.log_dir = Path(log_dir or os.environ.get("JEV_LOG_DIR") or Path.home() / ".local" / "state" / "jev-gateway")
        self.known_secrets = tuple(item for item in known_secrets if isinstance(item, str) and item)
        self.retention_seconds = _positive(retention_seconds, "retention_seconds")
        self.max_total_bytes = _minimum(max_total_bytes, "max_total_bytes", 32)
        self.max_record_bytes = min(_minimum(max_record_bytes, "max_record_bytes", 32), self.max_total_bytes - 1)
        self.max_segments = _positive(max_segments, "max_segments")
        self.clock, self.cleanup_interval_seconds = clock, _positive(cleanup_interval_seconds, "cleanup_interval_seconds")
        self.lock_timeout_seconds = _positive_float(lock_timeout_seconds, "lock_timeout_seconds")
        self._stop, self._thread, self._warned, self._closed = threading.Event(), None, False, False

    def record(self, event: str, *, state: Any = None, answers: Any = None,
               metadata: Mapping[str, Any] | None = None, exclusions: Sequence[str] | None = None) -> None:
        paths = validate_exclusions(exclusions)
        if self._closed:
            return
        try:
            record = {"timestamp": self.clock(), "event": str(event)[:128], "state": copy.deepcopy(state),
                      "answers": copy.deepcopy(answers), "metadata": copy.deepcopy(dict(metadata or {}))}
            _exclude(record, paths)
            encoded = _bounded_record(_filter(record, self.known_secrets), self.max_record_bytes)
            with self._locked_directory() as directory:
                now = self.clock()
                self._cleanup(directory, now)
                self._make_space(directory, len(encoded) + 1)
                self._write_segment(directory, encoded)
            self._start_cleanup()
        except Exception:
            self._warn()

    def close(self) -> None:
        self._closed, self._stop = True, self._stop
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1)

    def start(self) -> None:
        """Best-effort startup cleanup; construction itself never touches the filesystem."""
        if self._closed:
            return
        try:
            with self._locked_directory() as directory:
                self._cleanup(directory, self.clock())
            self._start_cleanup()
        except Exception:
            self._warn()

    def add_secret(self, value: str | None) -> None:
        if isinstance(value, str) and value and value not in self.known_secrets:
            self.known_secrets += (value,)

    def _locked_directory(self):
        return _DirectoryLock(self.log_dir, self.lock_timeout_seconds)

    def _cleanup(self, directory: Path, now: float) -> None:
        for path in _segments(directory):
            if now - path.stat().st_mtime > self.retention_seconds:
                path.unlink()

    def _make_space(self, directory: Path, incoming: int) -> None:
        if incoming > self.max_total_bytes:
            raise OSError("diagnostic record exceeds retention cap")
        entries = sorted(_segments(directory), key=lambda item: item.stat().st_mtime)
        total = sum(item.stat().st_size for item in entries)
        while entries and (total + incoming > self.max_total_bytes or len(entries) >= self.max_segments):
            path = entries.pop(0)
            total -= path.stat().st_size
            path.unlink()
        if total + incoming > self.max_total_bytes:
            raise OSError("diagnostic retention cap")

    def _write_segment(self, directory: Path, encoded: bytes) -> None:
        name = f"record-{time.time_ns()}-{os.getpid()}-{threading.get_ident()}.jsonl"
        path = directory / name
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            os.fchmod(fd, 0o600)
            data, written = encoded + b"\n", 0
            while written < len(data):
                count = os.write(fd, data[written:])
                if count <= 0:
                    raise OSError("short diagnostic write")
                written += count
        except Exception:
            try:
                os.unlink(path)
            except OSError:
                pass
            raise
        finally:
            os.close(fd)

    def _start_cleanup(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._cleanup_loop, daemon=True, name="jev-diagnostic-cleanup")
            self._thread.start()

    def _cleanup_loop(self) -> None:
        while not self._stop.wait(self.cleanup_interval_seconds):
            try:
                with self._locked_directory() as directory:
                    self._cleanup(directory, self.clock())
            except Exception:
                self._warn()

    def _warn(self) -> None:
        if self._warned:
            return
        self._warned = True
        try:
            sys.stderr.write("jev diagnostic logging unavailable\n")
        except Exception:
            pass


class _DirectoryLock:
    def __init__(self, directory: Path, timeout: float) -> None:
        self.directory, self.timeout, self.fd = directory, timeout, None
    def __enter__(self) -> Path:
        try:
            if self.directory.is_symlink(): raise OSError("unsafe diagnostic directory")
            existed = self.directory.exists()
            self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            info = self.directory.stat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or (existed and stat.S_IMODE(info.st_mode) != 0o700): raise OSError("unsafe diagnostic directory")
            lock = self.directory / ".lock"
            if lock.exists() and lock.is_symlink(): raise OSError("unsafe diagnostic lock")
            self.fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            info = os.fstat(self.fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1: raise OSError("unsafe diagnostic lock")
            os.fchmod(self.fd, 0o600)
            deadline = time.monotonic() + self.timeout
            while True:
                try:
                    fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return self.directory
                except BlockingIOError:
                    if time.monotonic() >= deadline: raise OSError("diagnostic lock unavailable")
                    time.sleep(0.005)
        except Exception:
            if self.fd is not None:
                os.close(self.fd)
                self.fd = None
            raise
    def __exit__(self, *_: Any) -> None:
        if self.fd is not None:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)


def _segments(directory: Path) -> list[Path]:
    result = []
    for path in directory.glob("record-*.jsonl"):
        try:
            info = path.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1:
            result.append(path)
    return result

def _positive(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value

def _positive_float(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    return float(value)

def _minimum(value: Any, name: str, minimum: int) -> int:
    value = _positive(value, name)
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value

def _exclude(record: dict[str, Any], paths: Sequence[tuple[str, ...]]) -> None:
    for parts in paths:
        current: Any = record
        for part in parts[:-1]:
            if isinstance(current, Mapping): current = current.get(part)
            elif isinstance(current, list) and part.isdigit() and int(part) < len(current): current = current[int(part)]
            else: current = None; break
        last = parts[-1]
        if isinstance(current, dict): current.pop(last, None)
        elif isinstance(current, list) and last.isdigit() and int(last) < len(current): current[int(last)] = "[EXCLUDED]"

def _filter(value: Any, secrets: Sequence[str]) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _filter(item, secrets) for key, item in value.items()
                if not _redacted_text(str(key), secrets)}
    if isinstance(value, list): return [_filter(item, secrets) for item in value]
    if isinstance(value, str):
        for secret in secrets: value = value.replace(secret, "[REDACTED]")
        return _CREDENTIAL.sub("[REDACTED]", value)
    return value

def _redacted_text(value: str, secrets: Sequence[str]) -> bool:
    return bool(_SENSITIVE_KEY.search(value) or _CREDENTIAL.search(value) or any(secret in value for secret in secrets))

def _bounded_record(record: Mapping[str, Any], maximum: int) -> bytes:
    try:
        encoded = json.dumps(record, allow_nan=False, separators=(",", ":"), default=lambda _: "[UNSERIALISABLE]").encode()
    except Exception:
        encoded = b""
    if len(encoded) <= maximum:
        return encoded
    for event_limit in (64, 16, 0):
        minimal = {"timestamp": record.get("timestamp"), "event": str(record.get("event", ""))[:event_limit], "truncated": True}
        encoded = json.dumps(minimal, separators=(",", ":")).encode()
        if len(encoded) <= maximum:
            return encoded
    return b'{"truncated":true}'
