# Spec and server review

## Findings

1. **High — expired records are not cleaned at startup.** `DiagnosticLogger.__init__` only saves configuration ([src/diagnostics.py:60-68](../../../src/diagnostics.py#L60)); cleanup starts after a successful `record` ([src/diagnostics.py:80-85](../../../src/diagnostics.py#L80)). An idle restarted gateway therefore leaves expired files indefinitely, contrary to the spec: “**Perform age cleanup at startup, before writing and periodically while running**.” The setup guide’s claim that an exited process removes records “at its next start” is consequently false ([SETUP_GUIDE.md:91](../../../SETUP_GUIDE.md#L91)).

2. **High — retention rotation can fail while removable records remain.** `_make_space` mutates `entries` inside `for path in entries` ([src/diagnostics.py:108-113](../../../src/diagnostics.py#L108)). With more than one record, Python advances past the shifted next item; a later cap check can raise even though deleting another old segment would admit the record. This fails the requirement to “**Enforce … a 20 MiB aggregate cap … across active and rotated logs**” and turns ordinary rotation into an avoidable lost diagnostic record.

3. **Medium — diagnostic segment discovery accepts hard links.** `_segments` rejects symlinks but accepts any regular `record-*.jsonl` path ([src/diagnostics.py:186-187](../../../src/diagnostics.py#L186)); unlike `.lock`, it never checks `st_nlink == 1`. Cleanup and cap accounting then trust a hard-linked file outside the log ownership model. This is incomplete against the spec’s “**safe file handling, including rejecting unsafe symlink destinations**” and its explicit simultaneous-process/private-log boundary; use the same regular-file, owner and single-link checks before accounting or unlinking segments.

No unwanted scope found in the reviewed server/docs. Server error wrapping and async tool handling appear consistent with the stated MCP boundary.

## Re-review after packaging fixes

The rotation loop and hard-link filtering are fixed ([src/diagnostics.py:119-123](../../../src/diagnostics.py#L119), [src/diagnostics.py:195-204](../../../src/diagnostics.py#L195)). Startup and multi-process tests were added, but three items remain unresolved:

1. **High — startup cleanup is still never invoked by production.** `DiagnosticLogger.start()` implements the fix ([src/diagnostics.py:95-104](../../../src/diagnostics.py#L95)), but neither gateway construction/evaluation ([src/gateway.py:119-155](../../../src/gateway.py#L119)) nor server startup calls it ([src/server.py:13-14](../../../src/server.py#L13)). Reproducer: create an expired `record-*.jsonl`, launch `src/server.py`, make no judgement; it remains. This still violates “**Perform age cleanup at startup**.”

2. **High — an injected logger does not learn the configured OpenRouter credential.** Gateway applies `known_secrets=(self.openrouter_api_key,)` only when it creates its own logger ([src/gateway.py:119](../../../src/gateway.py#L119)). `JevGateway(openrouter_api_key="custom-secret", logger=DiagnosticLogger(tempdir))` then logs `state="custom-secret"` unchanged because it is neither a recognised pattern nor in the injected logger’s secrets. This violates “**Filter known configured credentials**”; merge the gateway credential into every supplied logger’s filtering path without mutating caller inputs.

3. **High — the aggregate cap is not atomic across processes.** `record` releases `_DirectoryLock` after `_make_space` then writes the segment outside it ([src/diagnostics.py:80-85](../../../src/diagnostics.py#L80)). Two processes can both observe enough capacity, unlock, then both write and exceed 20 MiB. The new process test exists but has no barrier at that check/write window, so it does not establish the required “**20 MiB aggregate cap … simultaneous gateway processes**.” Keep capacity accounting and `O_EXCL` write under one lock (or recheck under lock immediately before commit).

Logging persistence failures otherwise remain best-effort: `record` catches filesystem/serialisation errors and the gateway does not use their result. Server error wrapping/state schemas appear correct. Unresolved items above require fixes before acceptance.

### Correction

The startup-cleanup finding is resolved in the current working tree: production `run()` invokes `gateway.logger.start()` before `app.run("stdio")` ([src/server.py:58-62](../../../src/server.py#L58)). The unresolved injected-logger credential and cross-process write-lock findings remain.

### Final closure review

Resolved. Gateway now calls `add_secret(self.openrouter_api_key)` for both default and injected loggers ([src/gateway.py:119-120](../../../src/gateway.py#L119)), so a caller-supplied `DiagnosticLogger` filters the configured credential. Capacity accounting and `_write_segment` now occur under the same directory lock ([src/diagnostics.py:81-86](../../../src/diagnostics.py#L81)); the multi-process cap test is present. `_DirectoryLock.__enter__` closes its descriptor on every acquisition failure ([src/diagnostics.py:179-203](../../../src/diagnostics.py#L179)), and segment writes loop to completion then unlink partial output on error ([src/diagnostics.py:131-150](../../../src/diagnostics.py#L131)). No unresolved diagnostics/server/docs findings remain from this review scope.

**Verdict provisional:** implementation inspection supports the fixes, but the diagnostics test count remains unchanged. Before acceptance, add deterministic regressions for an injected logger filtering the configured credential, concurrent check/write interleaving, file-descriptor closure on lock timeout, and partial-write cleanup. The existing multi-process test does not force the former race window.

### Final evidence review

The provisional evidence gap is closed. `tests/test_diagnostics.py` now supplies deterministic coverage for the injected arbitrary credential, a process paused within `os.write` while another writer waits, repeated lock-timeout descriptor accounting, partial writes, and invalid non-finite lock timeouts. The focused suite passes **18/18**. The startup regression invokes the production stdio launcher and confirms cleanup before `jev_health` ([tests/test_stdio.py:243](../../../tests/test_stdio.py#L243)); `run()` calls `logger.start()` before serving ([src/server.py:58](../../../src/server.py#L58)).

**Final verdict: accepted.** All prior diagnostics/server/docs findings are resolved; no unresolved items in this review scope.
