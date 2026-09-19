# Jev gateway setup guide

## Supported environment

The verified environment is Linux with Python 3.13 and OpenRouter only. Diagnostic locking requires POSIX facilities; Windows is unsupported. It uses the pinned runtime dependencies declared in `pyproject.toml`:

```text
httpx==0.28.1
mcp==2.2.0
pydantic==2.13.5
```

Create an isolated environment and install the local project:

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install .
```

Installation fetches packages and therefore needs network access. The project does not install dependencies itself. If the Python distribution created an environment without `pip`, provision `pip` through your normal Python-distribution process before running the installation command.

Set the OpenRouter credential only in the environment of the process that uses the gateway. The runtime reads this variable when it creates the client; no `.env` file is read automatically:

```bash
export OPENROUTER_API_KEY='replace-with-your-key'
```

The gateway does not load `.env`, does not support `TYPESAFE_API_KEY`, and never silently chooses a native TypeSafe route. A native-only key produces a `configuration` error; if both variables are present, routing remains OpenRouter.

## Start the MCP server

```bash
OPENROUTER_API_KEY='replace-with-your-key' .venv/bin/python src/server.py
```

MCP uses standard input and output, so do not add logging or shell banners to stdout. Configure your MCP host to launch the two absolute paths on its own machine, inheriting `OPENROUTER_API_KEY` from the host environment:

```toml
[mcp_servers.jev_gateway]
command = "/absolute/path/to/jev/.venv/bin/python"
args = ["/absolute/path/to/jev/src/server.py"]
```

The five tool names are `jev_check`, `jev_classify`, `jev_score`, `jev_evaluate` and `jev_health`. They accept JSON-compatible string, object and list state. Successful calls return validated judgements; failures return `{"error": {"category": "…", "message": "…"}}`.

`jev_health` is configuration-only unless its explicit verification option is supplied. Configuration-ready means a key and supported local configuration are present; it does not mean that OpenRouter has been contacted or is currently reachable.

## Call the Python client

```python
from src.gateway import JevGateway, JevGatewayError

gateway = JevGateway(model="~typesafe/jev-latest")
try:
    result = gateway.evaluate(
        state={"change": "remove a cache directory"},
        questions={
            "destructive": {
                "type": "noul",
                "instructions": "Does the change delete user data?",
            }
        },
    )
    print(result.answers)
except JevGatewayError as error:
    print(error.to_dict())
```

Use `check`, `choice` and `score` for one question. Input validation happens before a request is sent. The gateway rejects unsupported state, invalid or empty question definitions, non-finite numbers, oversized input, too many questions and malformed provider answers.

The stable error categories are:

| Category | Meaning |
| --- | --- |
| `input_validation` | Local request does not meet the contract. |
| `configuration` | OpenRouter configuration is absent or unsupported. |
| `authentication` | OpenRouter rejected credentials. |
| `rate_limit` | OpenRouter limited the request. |
| `timeout` | The bounded request deadline expired. |
| `provider_failure` | A transport or provider failure prevented a judgement. |
| `provider_response` | OpenRouter returned an invalid or incomplete judgement. |

Treat an error as no Jev judgement. The consuming project decides whether to stop, retry through its own policy, or proceed using its own judgement; that fallback is never a Jev approval.

## Limits, retries and diagnostics

The default total deadline is 20 seconds. It covers queueing, each attempt and backoff. The base API enforces a 256 KiB request limit, a 256 KiB provider-response limit, at most 64 questions and at most 8 simultaneous requests.

The gateway requests identity response encoding and rejects successful compressed responses before reading them. This keeps the 256 KiB response limit meaningful without decompressing an unbounded provider body locally.

The gateway makes at most three attempts for transient 408, 429, 502, 503 and 504 responses, connection errors and transport timeouts. Backoff starts at 0.25 seconds and doubles, while respecting a provider retry hint only inside the shared 20-second deadline. Replaying an inference can incur another charge.

Diagnostics are enabled by default in `$JEV_LOG_DIR` when set, otherwise in `~/.local/state/jev-gateway`. Records are private owner-only JSON files, each containing at most 64 KiB of JSON plus a newline, with a 20 MiB aggregate cap including newlines, 1,024-record cap and 24-hour retention. A record that exceeds its cap becomes a valid JSON record marked `"truncated": true`. Cleanup happens at server startup, before writes and every 60 seconds while running; an exited server removes expired records at its next start. Logging failures emit one sanitised stderr warning and do not replace a judgement.

The standalone MCP server uses the defaults above. When embedding the Python gateway, configure its constructor:

| Parameter | Default |
| --- | --- |
| `timeout_seconds` | `20.0` |
| `max_attempts` | `3` |
| `retry_backoff_seconds` | `0.25` |
| `max_in_flight` | `8` (excess calls receive an immediate error) |
| `max_questions` | `64` |
| `request_limit_bytes` / `response_limit_bytes` | `262144` each |

For example, `JevGateway(timeout_seconds=5, max_attempts=2)` uses a five-second inference budget and at most two attempts. Async applications use `aevaluate`, `acheck`, `achoice` and `ascore`; the synchronous wrappers cannot run inside an existing event loop.

An optional `logger=DiagnosticLogger(...)` argument configures `log_dir`, `retention_seconds`, `max_total_bytes`, `max_record_bytes` and `max_segments`. Import that class from `src.diagnostics`. The gateway adds its configured key to the logger's automatic exclusions. Use the gateway as a context manager or call `close()` to stop its cleanup worker; embedded applications can call `gateway.logger.start()` explicitly for cleanup before their first request.

Pass `logging_exclusions` as a list of RFC 6901 JSON Pointer strings rooted at the full diagnostic record: `/state`, `/answers`, or `/metadata`. For example, `/state/customer/token` excludes that nested field from the diagnostic copy. Use `~1` for `/` and `~0` for `~`; malformed pointers are rejected as input errors before inference.

Before submitting state, remove credentials and anything you do not intend to send to OpenRouter. Logging exclusions affect only a diagnostic copy; they do not alter inference state. Automatic filtering is best effort, including for nested data and returned answers, and cannot guarantee that every secret is detected.

## Examples and verification

Both public examples make a live provider request only when `OPENROUTER_API_KEY` is present:

```bash
OPENROUTER_API_KEY='replace-with-your-key' .venv/bin/python examples/demo_openrouter_decisions.py
OPENROUTER_API_KEY='replace-with-your-key' .venv/bin/python examples/coding_agent_eval.py
```

They report only sanitised structured gateway errors. They are not part of the offline test suite.

Run offline verification with synthetic credentials and the test fake transport:

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q src examples
.venv/bin/python -c "from src.gateway import JevGateway; from src import server; print('imports ok')"
```

No linter or type checker is declared or installed in this repository. Fresh-install verification remains unperformed because dependency installation was not authorised. A live smoke test is separate and requires an intentional credential-bearing, potentially chargeable provider request.

## Legacy material

`examples/demo_typesafe_sdk.py`, if present in a local historical checkout, and any TypeSafe instructions are legacy material outside the supported gateway contract. `prototypes/antirabbithole/` is also preserved as a separate prototype: it owns any supervisory policy and is not a gateway test or integration.
