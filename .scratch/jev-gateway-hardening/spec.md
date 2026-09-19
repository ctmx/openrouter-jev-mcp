# Jev gateway hardening

**Status:** ready-for-agent

**Task ID:** jev-gateway-hardening-20260919

## Problem Statement

The owner has a small, reusable Jev gateway and local MCP server, previously exercised against
OpenRouter. It needs dependable failure behaviour, private diagnostic logging and reproducible
installation before other agents rely on its judgements to authorise or block actions.

The inspected baseline silently accepts absent answers as empty dictionaries, selects native
TypeSafe when both provider keys exist, and reports health as online without contacting the
provider. It has no gateway offline test suite or dependency manifest. Its general MCP evaluate
tool accepts only object state despite the underlying client supporting strings and lists.
Existing prototype examples are not evidence that the gateway satisfies this specification.

## Solution

Provide a local, single-user, stdio MCP gateway and Python client backed by OpenRouter. Retain
the five Jev tools, validate the full request/result boundary, and return explicit errors when a
valid judgement cannot be obtained. Bound requests and retries by one configurable total deadline.

Keep action policy in consuming projects. They may use valid judgements to authorise or block
actions and may use their own judgement following an explicit gateway error. The gateway must
never describe that fallback as a Jev approval.

Record useful filtered state and answers locally, with caller logging exclusions and bounded
retention. Make the installation and offline verification reproducible.

## User Stories

1. As the owner, I want local agents under my account to use the gateway, so that no network service needs administering.
2. As a consuming agent, I want the existing five MCP tool names, so that integrations remain recognisable.
3. As a Python caller, I want a reusable client, so that using Jev does not require MCP.
4. As the owner, I want OpenRouter to be the sole supported provider in this pass, so that routing is predictable.
5. As a caller, I want missing configuration reported clearly, so that I can distinguish it from provider failure.
6. As a caller, I want model configuration retained, so that I can choose a compatible Jev model explicitly.
7. As a caller, I want to submit string, object or list state, so that I need not invent transport wrappers.
8. As a caller, I want Noul propositions checked, so that I receive validated yes/no probabilities.
9. As a caller, I want Choice options validated, so that answers refer to my supplied labels.
10. As a caller, I want Score rubrics validated, so that results correspond to my ordered levels.
11. As a caller, I want custom question maps validated, so that multiple questions have attributable answers.
12. As a caller, I want missing or malformed provider answers rejected, so that empty data cannot look successful.
13. As a caller, I want invalid and excessive requests rejected before transmission, so that mistakes do not cause avoidable provider work.
14. As a caller, I want oversized provider responses bounded, so that upstream output cannot exhaust local memory.
15. As a consuming project, I want to own action policy, so that permission thresholds fit each action's consequences.
16. As a consuming project, I want explicit error categories, so that I can apply my own fallback policy.
17. As the owner, I want a configurable 20-second total deadline, so that unavailable inference cannot hold agents indefinitely.
18. As the owner, I want limited retries for transient failures, so that brief provider problems can recover within that deadline.
19. As the owner, I want retry behaviour documented, so that possible duplicate charges are visible.
20. As a caller, I want configuration readiness distinguished from live connectivity, so that health reporting is truthful.
21. As the owner, I want broad state content support, so that the gateway does not impose a project-specific content policy.
22. As a consuming agent, I want responsibility for excluding credentials before submission, so that credentials are not intentionally sent for inference.
23. As the owner, I want state and answers in diagnostic records, so that I can investigate incorrect judgements.
24. As the owner, I want automatic credential filtering, so that recognisable credentials are excluded from those records.
25. As a caller, I want to exclude selected fields from logs, so that additional sensitive values are not persisted.
26. As a caller, I want logging exclusions to leave inference content unchanged, so that diagnostics do not change the question being answered.
27. As the owner, I want private log files, so that other local accounts cannot read diagnostic content through permissive defaults.
28. As the owner, I want a 24-hour and 20 MiB retention limit, so that troubleshooting does not accumulate an indefinite sensitive archive.
29. As the owner, I want decisions to continue when logging fails, so that diagnostics do not become an availability requirement.
30. As an MCP client, I want stdout reserved for protocol traffic, so that warnings do not corrupt the connection.
31. As a maintainer, I want offline behavioural tests, so that verification neither needs real credentials nor incurs inference charges.
32. As a new user, I want a reproducible installation and accurate examples, so that the gateway works outside its original virtual environment.

## Implementation Decisions

### Confirmed scope and policy

- Support trusted local agents running under the owner's account, through stdio MCP and direct Python use. No listener or multi-user authentication system is required.
- OpenRouter is the only supported backend for this pass. Keep the existing Jev default model unless primary-source contract verification demonstrates incompatibility. Do not silently fall back to native TypeSafe.
- Preserve the five tool names: `jev_check`, `jev_classify`, `jev_score`, `jev_evaluate` and `jev_health`. Preserve successful OpenRouter client/tool behaviour where compatible with strict validation. Native TypeSafe is outside the supported contract; document that change explicitly.
- The gateway handles judgements, transport, validation and diagnostics. Consuming projects own thresholds, action permissions and fallback following errors, including permission to proceed using their own judgement.
- Accept arbitrary supported state content; do not add a content classifier or project-specific censorship. Callers must exclude credentials before sending state. Logging filtering is defence in depth and does not guarantee detection of arbitrary secrets.

### Request and response contract

- Align accepted state types between MCP and Python: JSON-compatible strings, objects and lists. Reject non-serialisable values and non-finite numbers. Reject empty/invalid propositions, question maps, options and rubrics rather than coercing them silently.
- Confirm the OpenRouter Decisions request/response schema against official sources before implementing validators. Keep schema facts and fixtures grounded in those sources; do not invent confidence fields, normalisation rules or score units from informal descriptions.
- Require all requested answers and the correct answer type. Validate numeric ranges and finite probabilities, option membership and rubric bounds according to that verified contract. Missing answers or invalid provider data produce an explicit provider-response error, never an empty success or a default probability.
- Define stable, sanitised error categories covering configuration, input validation, timeout, authentication, rate limiting, provider availability and invalid provider responses. Python callers and MCP clients must be able to distinguish an error from a valid judgement.
- Preserve cancellation and ensure clients/transports are closed. Bound request size, response size, question count and in-flight requests. Reject excess predictably before allocating or sending unbounded data.
- Diagnostic/error paths must not include authorization headers, configured credentials or unfiltered provider error bodies.

### Deadlines and retries

- Default to a configurable 20-second total request deadline. All attempts, connection/read/write waits, queue waits and backoff share the same budget. Per-attempt timeouts alone do not satisfy this requirement.
- Use a finite attempt limit and explicit transient-failure allowlist. Respect applicable retry delay hints only within the remaining budget. Do not retry invalid input, authentication failures or malformed successful responses.
- No new attempt starts after the budget is exhausted. Make the retry policy testable without real sleep. Document that replaying a submitted inference request may incur another charge; do not claim exactly-once processing.

### Diagnostic logging

- Log bounded state, answers and operational metadata in a private owner-controlled directory. Keep stdout exclusively for MCP. Use sanitised stderr warnings for diagnostic failures.
- Apply automatic filtering to known configured credentials, sensitive field names and recognisable credential patterns before serialising any diagnostic data. Filter nested structures and returned answers as well as input state. Never log request authorization headers.
- Add optional caller-supplied logging exclusions, available to both Python and MCP callers, with documented nested-field semantics. Validate exclusion specifications before inference; never silently ignore an invalid specification. Apply exclusions only to a logging copy, leaving caller inputs and inference payloads unchanged.
- Retain logs for at most 24 hours and at most 20 MiB aggregate, enforcing whichever limit is reached first. Account for active and rotated records, UTF-8 byte size and simultaneous local gateway processes. Bound individual records and mark truncation explicitly.
- Apply private directory/file permissions and safe file handling, including rejecting unsafe symlink destinations. Failures to establish a safe log location leave decisions available and emit a sanitised warning.
- Perform age cleanup at startup, before writing and periodically while running. Document that an exited process cannot remove files while stopped; remove expired records on the next startup. Do not introduce a background system service solely for cleanup.
- Logging errors, full disks and permission failures do not replace successful judgements with failures. Warning generation must itself be bounded and omit state, answers and credentials.

### Health and installation

- Separate local configuration readiness from verified provider connectivity. A configuration-only check must state that connectivity is unverified. A live probe is explicit, uses non-sensitive synthetic state, and shares timeout/error rules; do not probe on import or server startup.
- Declare supported Python and dependency versions and reproducible install/test commands. Inspect installed capabilities first; adding a manifest does not authorise installing or upgrading dependencies.
- Correct examples and setup guidance so they do not assume an existing virtual environment, automatically loaded environment files, embedded keys or a personal absolute path. Document external inference, logs, limits, routing, health semantics and migration from native TypeSafe.

### Engineering defaults to settle in implementation

The owner authorised unattended execution of this flow after the interview. The implementer may
select concrete finite size/count/concurrency limits, retry attempt count/backoff and the precise
logging-exclusion syntax without reopening product questions. Record those choices in user-facing
configuration documentation and test their boundaries. They must preserve every confirmed requirement
above. The 20-second deadline and 24-hour/20 MiB retention limits are fixed agreed defaults.

## Testing Decisions

- Use the public Python gateway API as the principal behavioural seam, substituting only the external OpenRouter transport. Assert returned judgements, errors, captured provider requests and observable diagnostic records, not internal helper calls or class structure.
- Add a small stdio MCP integration suite covering discovery of all five tools, state schemas, successful results, protocol errors, truthful health and stdout cleanliness. Reuse the fake provider underneath the real gateway so integration tests exercise the implementation.
- Use synthetic credentials, temporary log directories, controlled time and deterministic provider responses. Normal tests must neither load owner credentials nor call a live provider.
- Existing prior art is limited to live demo scripts and an isolated anti-rabbit-hole scenario script that prints outcomes; it is not an offline gateway regression suite. Do not expand that prototype to satisfy this spec.
- Cover every primitive and mixed question maps, invalid input without outbound calls, missing/wrong-type answers, out-of-range/non-finite values, provider failures, missing configuration and unsupported native-provider configuration.
- Demonstrate the total deadline across retries and backoff, bounded attempt counts, response-size and concurrency limits, cancellation, and cleanup of transports.
- Demonstrate nested credential filtering and logging exclusions with sentinel secrets, unchanged inference payloads, bounded records, byte/age rotation, simultaneous writers, permissions and unsafe paths.
- Demonstrate continued successful decisions when log operations fail, plus a sanitised stderr warning and clean MCP stdout.
- Add installation/import/startup checks using the available environment. Use the declared formatter/linter/type checker if available; report missing tools rather than installing them without approval.
- Run focused tests during each slice, the complete offline gateway suite once at completion, and standards/spec review before committing implementation. Keep prototype live examples outside default test collection.
- A live provider smoke test is separate, optional verification requiring explicit owner approval for credential access and paid requests. Offline passing tests do not prove live availability.

## Out of Scope

- Anti-rabbit-hole supervision, migrating its prototype, and consuming-project permission policies.
- Native TypeSafe implementation/support, provider failover and additional model providers.
- Network listeners, remote access, multiple local security principals, deployment and remote CI changes.
- Dependency installation/upgrades, access to real credentials, paid provider requests or remote writes without explicit approval.
- Perfect secret detection, mandatory audit logging, telemetry services and new background infrastructure.
- Unrelated refactoring, deleting existing prototypes or modifying the delegation plugin to unblock this task.

## Further Notes

The owner explicitly requested the unattended sequence setup → spec → tickets → implementation
on 2026-09-19, preferring DELEGATE_AGY to conserve Codex tokens and requiring verified results.
That instruction supplies routine local setup choices: local Markdown tracking, default triage
labels, a single glossary and the proposed public-API/MCP test seams. It does not waive safety gates.

The installed delegation plugin's adapters were unavailable. The owner subsequently explicitly
rejected delegate-codex-agy for this task and authorised ordinary native Codex delegation to
gpt-5.6-terra. That route supersedes the plugin preference without claiming its lifecycle guarantees.
See the feature progress record for current workers, checks and independent review evidence.
