# 04: Deliver a reproducible and verified hardened gateway

**What to build:** A new local user can install, configure and run the hardened gateway using accurate instructions, while maintainers can reproduce its offline verification and understand remaining live-provider limits.

**Blocked by:** 01 — Validated OpenRouter judgements; 02 — One deadline and bounded retries; 03 — Filtered bounded local logs.

**Status:** done

- [x] Declare supported Python/dependency versions and reproducible installation, focused-test, full offline-test and available static-check commands using the smallest appropriate existing toolset.
- [x] Dependency declarations reflect actual runtime imports and the supported MCP interface; no installation or upgrade is performed without owner approval.
- [x] Verify import and stdio startup in the available environment and describe any fresh-install verification still requiring approved dependency installation.
- [x] Update public examples and setup guidance for explicit environment configuration, portable paths and the OpenRouter-only support boundary. Do not imply environment files load automatically unless implemented.
- [x] Document input/output and error contracts, resource limits, deadline/retry behaviour, optional health probing, logging exclusions, retention, truncation and logging failure behaviour.
- [x] Explain that state is transmitted to OpenRouter, callers must exclude credentials, filtering is imperfect, and consuming projects own action decisions and may apply their own fallback following gateway errors.
- [x] Keep anti-rabbit-hole prototypes outside the gateway's default tests and scope; preserve them without unrelated fixes or removal.
- [x] Run the complete offline gateway suite after the integrated slices, plus relevant available lint/type checks, and investigate failures. Record precise commands and outcomes.
- [x] Complete standards and specification review of the final implementation using the owner-authorised route and required independent verifier if delegated; resolve findings before acceptance.
- [x] Verify acceptance against all parent-spec requirements, inspect the final diff and commit approved local work to the current branch without push or other remote writes.
- [x] Report live-provider verification separately; offline success must not be presented as proof of current upstream connectivity or paid model performance.

## Testing seam

Reuse the established public API and stdio suite. Add only installation/import/startup checks necessary to demonstrate documented use; do not create tests that merely mirror documentation or configuration text.

## Completion evidence

The full 51-test offline suite passes in 35.213 seconds, with isolated environment and temporary logs outside the faulty sandbox. Compilation, imports, manifest parsing and diff checks pass. Standards and specification reviews have no unresolved findings. Fresh installation, live inference and absent lint/type tools remain explicitly unverified; no dependency installation or remote write occurred. The local completion commit includes these records.
