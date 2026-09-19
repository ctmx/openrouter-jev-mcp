# Jev gateway

Jev gateway is a local Python client and stdio MCP server for structured Jev judgements through OpenRouter. It supports Noul, Choice, Score and question-map evaluations. It makes judgements; a consuming project owns action thresholds, permissions and any fallback after an error.

OpenRouter is the only supported provider. Native TypeSafe keys and SDK routes are not supported by this gateway.

## Install

Use Python 3.13 on Linux. Diagnostic file locking uses POSIX facilities; Windows is not supported. The declared runtime versions are `httpx==0.28.1`, `mcp==2.2.0` and `pydantic==2.13.5`.

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install .
```

This installs dependencies from the network. It is a user action. The gateway reads its key from the process environment only when it runs; this work did not access any real credential. Set the key explicitly before a live call or server launch:

```bash
export OPENROUTER_API_KEY='replace-with-your-key'
```

No `.env` file is loaded automatically. State is sent to OpenRouter for inference, so callers must exclude credentials and anything they do not intend to send externally. Diagnostic filtering is defence in depth and cannot detect every secret.

## Python client

```python
from src.gateway import JevGateway, JevGatewayError

gateway = JevGateway()
try:
    answer = gateway.check(
        state={"proposed_action": "delete a temporary cache directory"},
        proposition="Does the action delete data outside the project?",
    )
except JevGatewayError as error:
    print(error.to_dict())
```

`evaluate(state, questions)` accepts JSON-compatible strings, objects and lists and returns a `DecisionResult` with `model`, `answers`, `usage` and `raw_response`. `check`, `choice` and `score` return the requested answer. Questions and returned answers are validated; no missing or malformed answer is treated as success.

Failures are structured as `{"error": {"category": ..., "message": ...}}`. Categories are `input_validation`, `configuration`, `authentication`, `rate_limit`, `timeout`, `provider_failure` and `provider_response`. Messages are sanitised and do not include credentials or provider response bodies.

The default request deadline is 20 seconds. Current input boundaries are 256 KiB per request, 256 KiB per provider response, 64 questions and 8 in-flight requests. See [SETUP_GUIDE.md](SETUP_GUIDE.md) for retry and diagnostic-record configuration.

## MCP server

Run the server over standard input and output:

```bash
OPENROUTER_API_KEY='replace-with-your-key' .venv/bin/python src/server.py
```

The server keeps stdout for MCP protocol traffic. It exposes `jev_check`, `jev_classify`, `jev_score`, `jev_evaluate` and `jev_health`. Tool calls accept the same state types as the Python client and return either a successful result or the structured error object above.

`jev_health` reports local configuration readiness by default. It does not prove OpenRouter connectivity unless its explicit verification option is requested; a live probe uses the same timeout and error rules as a judgement.

To configure an MCP host, run the installed virtual environment’s Python executable with the repository’s `src/server.py` as its argument. Start the MCP host from an environment that already contains `OPENROUTER_API_KEY`; the server inherits it. For example:

```toml
[mcp_servers.jev_gateway]
command = "/absolute/path/to/jev/.venv/bin/python"
args = ["/absolute/path/to/jev/src/server.py"]
```

Use absolute paths appropriate to the machine; no personal path is assumed. The existing anti-rabbit-hole prototype is separate from this gateway and is not part of its default tests or policy.

## Verification

Offline tests use synthetic credentials and a fake transport; they do not call OpenRouter. After installation, run:

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q src examples
.venv/bin/python -c "from src.gateway import JevGateway; from src import server; print('imports ok')"
```

The repository currently declares no formatter, linter or type checker, and none is installed by this package. Fresh-install verification was not run because dependency installation was not authorised. A passing offline suite does not demonstrate present OpenRouter connectivity or paid-model behaviour. Run either example only when you intentionally authorise a live provider request:

```bash
OPENROUTER_API_KEY='replace-with-your-key' .venv/bin/python examples/demo_openrouter_decisions.py
```
