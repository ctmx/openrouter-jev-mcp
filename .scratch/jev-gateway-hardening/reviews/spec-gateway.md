# Spec review: gateway core and resilience

## Findings

1. **High — request-size limiting occurs after an unbounded serialisation.** Ticket 01 requires finite request limits and the parent spec says to reject excess “before allocating or sending unbounded data”. [`src/gateway.py:160-164`](../../../src/gateway.py) builds `payload` and `_json_bytes` serialises all of it before comparing its byte length. A synthetic state containing a multi-hundred-MiB string will be copied into the JSON string before the 256 KiB limit rejects it. This defeats the intended local memory bound.

2. **High — compressed provider responses can decompress beyond the response cap before this code counts bytes.** Ticket 01 requires bounding response reading before buffering an excessive body. [`src/gateway.py:219-220`](../../../src/gateway.py) uses HTTPX `aiter_bytes()`, whose normal behaviour is to decode content encodings, then `_read_limited_async` counts decoded chunks. A small `Content-Encoding: gzip` response that expands past the cap may be decompressed by HTTPX before the limit check; the current test only supplies an already-uncompressed oversized body. Read raw bounded bytes or explicitly constrain decoded streaming behaviour.

3. **Medium — an oversized retryable error response is classified as `provider_response`, not its stable HTTP category.** The contract requires distinguishable rate-limit/timeout/provider failures. The body is read before [`_http_error`](../../../src/gateway.py:220-225), so a 429/503 whose body crosses the configured limit raises `JevProviderResponseError`; retry and category handling never run. Reproduce with a 429 `MockTransport` body larger than `response_limit_bytes`. Classify status before reading a bounded diagnostic-free body, while still closing the stream.

4. **Medium — retry semantics treat every `httpx.HTTPError` as transient.** Ticket 02 requires an explicit transient-failure allowlist. [`src/gateway.py:226-229`](../../../src/gateway.py) retries all `HTTPError`s, including protocol errors that are not demonstrably transient. The documented allowlist names statuses and “transport timeouts”; narrow this to explicitly selected connection/timeout failures or document the broader class and prove it is safe.

No other core/resilience deviations found in the staged diff: the public contract validation, sanitised error messages, response stream context management, cancellation tests, non-blocking in-flight overload, and health readiness/probe split align with tickets 01/02.

## Re-review resolution

All four findings above are resolved in the current working-tree candidate.

- [`_preflight_json_bytes`](../../../src/gateway.py#L295) now walks the already-validated request graph and rejects a conservative encoded-size estimate before `_json_bytes` materialises the body. It runs before outbound work; question-count validation remains finite, and question normalisation only makes shallow bounded-map/list copies.
- [`_post`](../../../src/gateway.py#L210) requests `Accept-Encoding: identity` and rejects a successful non-identity `Content-Encoding` before reading it. The new compressed-success regression covers that boundary.
- HTTP status is now classified before body consumption ([`src/gateway.py:220-228`](../../../src/gateway.py#L220)); the oversized-429 retry regression confirms that a retryable status retains its category and retry path.
- The exception branch retries only `httpx.TimeoutException` and `httpx.ConnectError`; other `HTTPError` instances fail immediately. The protocol-error regression confirms the explicit transient allowlist.

**Final verdict: pass for the four previously reported core/resilience findings.**

## Final preflight closure

The latest candidate moves preflight ahead of `_questions` and `_state` ([`src/gateway.py:159-164`](../../../src/gateway.py#L159)), so oversized raw state or question content is rejected before normalisation copies. `_bounded_utf8_length` counts Unicode code points into UTF-8 byte lengths without allocating an encoded copy and stops as soon as the remaining budget is exceeded ([`src/gateway.py:317-325`](../../../src/gateway.py#L317)). This resolves the remaining allocation-order concern. **Final verdict remains pass.**
