# 03: Diagnose decisions with filtered, bounded local logs

**What to build:** Callers can diagnose Jev judgements using private local state/answer records, with automatic credential filtering, caller-supplied logging exclusions, 24-hour/20 MiB retention and continued decision availability when logging fails.

**Blocked by:** 01 — Return validated OpenRouter judgements through Python and MCP.

**Status:** done

- [x] Record bounded state, answers and operational metadata for requests and outcomes in a private owner-controlled log directory; reserve stdout for MCP traffic.
- [x] Filter known configured credentials, sensitive field names and recognisable credential patterns in nested state, answers and diagnostic metadata before serialisation; never log authorization headers or unfiltered provider errors.
- [x] Add optional caller-supplied logging exclusions to Python and MCP interfaces, with documented nested-field semantics. Reject invalid specifications rather than silently ignoring them.
- [x] Apply exclusions and filtering to logging copies only. Tests prove caller inputs and provider-bound state are unchanged, and excluded values are absent from all emitted diagnostics.
- [x] Enforce 24-hour retention and a 20 MiB aggregate cap across active and rotated logs, accounting for encoded byte sizes, bounded individual records and simultaneous gateway processes.
- [x] Mark truncated diagnostic content explicitly and demonstrate that a single oversized record cannot defeat the aggregate cap.
- [x] Perform age cleanup at startup, before writing and periodically while running; document that cleanup resumes on restart after the process has been stopped.
- [x] Create restrictive directory/file permissions and handle unsafe destinations, including symlinks, without disclosing log content or changing unrelated files.
- [x] A disk-full, permission, rotation or serialisation failure leaves valid decisions available and produces a bounded, sanitised stderr warning. Warning failure cannot recursively break decision handling.
- [x] Offline tests use temporary files, controlled time and synthetic sentinel secrets to cover age/byte boundaries, simultaneous writes, nested exclusions, permissions, unsafe destinations and failure paths.
- [x] Demonstrate logging behaviour through the public Python API and representative stdio MCP calls. Explain that callers must exclude credentials before submission and automatic filtering cannot recognise every secret.

## Testing seam

Use the public request interfaces, then inspect observable records and stderr in temporary directories. Use filesystem fault injection only where needed to prove behaviour that cannot be reproduced reliably with ordinary permissions.

## Completion evidence

All 18 diagnostics tests pass, including injected-key filtering, startup and active retention, deterministic inter-process cap enforcement, lock descriptor cleanup and short writes. Real stdio tests verify logging exclusions and continued decisions on logging failure.
