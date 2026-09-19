# 01: Return validated OpenRouter judgements through Python and MCP

**What to build:** Callers can use all five existing tools and the Python client with predictable OpenRouter routing, validated requests and judgements, explicit errors, and truthful health information. Establish the offline behavioural test harness with this working slice.

**Blocked by:** None (can start immediately once an execution route is available).

**Status:** done

- [x] Confirm the Decisions request and response contract against official primary sources; record source/version evidence and construct synthetic fixtures without real credentials.
- [x] Preserve the five existing tool names and supported successful OpenRouter behaviours. Support JSON-compatible string, object and list state consistently across Python and MCP.
- [x] Route exclusively to OpenRouter. Missing configuration and unsupported native-only configuration produce clear sanitised errors; an additional native key cannot change the provider.
- [x] Validate propositions, named question maps, Choice options and Score rubrics before any outbound request. Reject invalid, non-finite and non-serialisable values without coercing them into instructions.
- [x] Implement and document finite request byte, question count and response byte limits. Bound response reading before buffering an excessive body.
- [x] Validate every requested answer's presence, primitive type and contract-defined numeric/label/rubric constraints. Missing answers and malformed provider data are explicit failures, never empty success values.
- [x] Provide distinguishable Python and MCP errors for configuration, invalid input, authentication, rate limiting, timeout, provider failure and malformed responses, without exposing headers or raw error bodies.
- [x] Health distinguishes configured readiness from verified connectivity. Optional live verification uses synthetic state and the gateway's transport rules; import/startup does not trigger inference.
- [x] Offline public-API tests cover every primitive, mixed question maps, request rejection, valid/invalid responses and configuration cases using a fake OpenRouter transport.
- [x] A real stdio MCP test covers tool discovery, schemas, representative successes/errors and stdout cleanliness against the fake provider.
- [x] Document runnable focused test and available static-check commands. Existing live prototypes are outside normal test discovery.

## Testing seam

Use the public gateway API and a small stdio MCP suite, substituting the external provider transport. Assert caller-observable outcomes and captured requests. Prefer the existing public interfaces over new internal test APIs.

## Comments

The parent hardening spec is authoritative. Specification readiness does not resolve the execution-route blocker recorded in the feature progress record.

## Completion evidence

Public gateway validation and real stdio discovery/calls/errors pass in the 51-test offline suite. Provider contract evidence is retained in the feature contract note; the alpha route was not live-probed.
