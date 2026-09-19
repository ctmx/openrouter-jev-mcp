# 02: Keep decisions within one deadline during transient failures

**What to build:** Python and MCP callers receive a valid judgement or explicit failure within a configurable total budget, with limited recovery from transient provider failures and bounded simultaneous work.

**Blocked by:** 01 — Return validated OpenRouter judgements through Python and MCP.

**Status:** done

- [x] Default to a configurable 20-second total deadline covering queue time, network phases, retry attempts and backoff; validate configuration values.
- [x] Set and document a finite retry attempt limit and an explicit transient-failure allowlist grounded in the provider contract.
- [x] Retry only while both attempt and deadline budgets permit. Respect retry-delay hints within the remaining budget; never begin an attempt after exhaustion.
- [x] Do not retry invalid input, authentication failures or malformed successful responses. Expose exhausted retries as explicit errors, not model answers.
- [x] Implement a documented finite in-flight limit with deadline-aware waiting or an explicit overload error; verify the observable limit under simultaneous requests.
- [x] Cancellation stops subsequent work and cleanup closes owned clients/transports on normal and exceptional exits.
- [x] Tests with controlled time and fake provider responses demonstrate transient recovery, exact attempt bounds, budget exhaustion across multiple phases and prompt cancellation without real sleeps.
- [x] Exercise representative retries and timeout failures through the stdio MCP boundary as well as the public Python API.
- [x] Document that retrying submitted inference can duplicate charges and does not guarantee exactly-once execution.

## Testing seam

Extend the public-API/MCP harness from ticket 01. Control time and provider behaviour at external boundaries; test elapsed budget and observable outcomes rather than helper call sequences.

## Completion evidence

Resilience tests cover explicit retries, retry hints, total deadlines, streaming cancellation/closure, caller cancellation, overload recovery and non-transient failures. Independent gateway review accepted the corrected resource bounds.
