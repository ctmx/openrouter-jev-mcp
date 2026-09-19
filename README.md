# openrouter-jev-mcp

[![MCP](https://img.shields.io/badge/MCP-stdio-blue.svg)](https://modelcontextprotocol.io/)
[![Python 3.13](https://img.shields.io/badge/python-3.13-brightgreen.svg)](https://www.python.org/)
[![Provider: OpenRouter](https://img.shields.io/badge/Provider-OpenRouter-purple.svg)](https://openrouter.ai/)
[![Model: Jev Latest](https://img.shields.io/badge/Model-~typesafe%2Fjev--latest-orange.svg)](https://openrouter.ai/~typesafe/jev-latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> **A Python decision gateway and Model Context Protocol (MCP) server for TypeSafe's Jev model through OpenRouter.**

An independent community project, unaffiliated with TypeSafe or OpenRouter. The supported environment is Linux with Python 3.13; Windows is unsupported because diagnostic locking uses POSIX facilities.

---

## ⚡ What is This?

Coding agents repeatedly encounter small, bounded questions that can benefit from a separate model judgement:

```text
               "Is this bug most likely:
      code_defect / stale_test / network_timeout?"
                          │
                          ▼
                   ┌──────────────┐
                   │   Jev AI     │  Typed decisions
                   │  Judge via   │  Caller-defined questions
                   │  OpenRouter  │  Probabilities
                   └──────┬───────┘
                          │
          network_timeout (p = 0.94)
                          │
                          ▼
          Caller applies its own action policy
```

**TypeSafe AI's Jev** returns typed, probabilistic decisions for software rather than free-form prose. [TypeSafe documents](https://docs.typesafe.ai/introduction) three question types: Choice, Score and Noul. The probabilities above are illustrative; a judgement can be wrong and does not grant permission to act.

### Why OpenRouter?
The gateway uses an OpenRouter key with the alpha Decisions endpoint (`https://openrouter.ai/api/alpha/decisions`) and the `~typesafe/jev-latest` alias. Native TypeSafe keys and SDK routing are not supported. The endpoint is alpha; availability and its contract may change.

On 19 September 2026, [OpenRouter listed Jev 1.13](https://openrouter.ai/typesafe/jev-1.13) at $0.042 per million input tokens and $0 for output, with approximately 260 ms median provider latency. These are provider figures, not gateway benchmarks or guarantees. Check the listing for current pricing; requests and retries can incur charges.

---

## 🛠️ MCP Tools Exposed

This server runs over standard `stdio` and implements the MCP specification:

| Tool | Jev Primitive | Use Case | Return Value |
| :--- | :--- | :--- | :--- |
| `jev_check` | **Noul** | Yes / No propositions | Calibrated probability $P(\text{true}) \in [0.0, 1.0]$. |
| `jev_classify` | **Choice** | Categorizing state into a closed set of labels | Chosen label, full probability distribution, and confidence ($0.0–1.0$). |
| `jev_score` | **Score** | Placing state along an ordered discrete rubric | Expected score index and confidence score. |
| `jev_evaluate` | **Multi-Question** | Evaluating an arbitrary dictionary of Choice, Score, and Noul questions simultaneously in one parallel pass | Dictionary of typed answers and token usage. |
| `jev_health` | **Diagnostics** | Local configuration readiness; optional live probe | Readiness, configured model and connectivity status. Connectivity is unverified unless `verify=true` is requested. |

Failures return `{"error": {"category": "…", "message": "…"}}`. Treat an error as no judgement. See the [setup guide](SETUP_GUIDE.md) for error categories, limits and configuration.

---

## 🚀 Quick Start

### 1. Prerequisites
* Linux with Python 3.13 (optionally managed with [uv](https://docs.astral.sh/uv/))
* An [OpenRouter API Key](https://openrouter.ai/keys)

### 2. Installation & Setup
Clone the repository and install dependencies:

```bash
git clone https://github.com/ctmx/openrouter-jev-mcp.git
cd openrouter-jev-mcp

# Using uv (recommended):
uv venv --python 3.13 .venv
source .venv/bin/activate
uv pip install -e .

# Or standard pip:
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Choose one installation method above. To configure a key, copy the environment template, restrict its permissions, then edit it locally:
```bash
cp .env.example .env
chmod 600 .env
# Edit .env with your actual key:
# OPENROUTER_API_KEY=sk-or-v1-...
```

### 3. Verify Live Connectivity
The gateway does not load `.env` automatically. In Bash, load only your own trusted file before running the example. This sends the example's state to OpenRouter and may incur a charge:
```bash
set -a
source .env
set +a
python examples/demo_openrouter_decisions.py
```

---

## 🤖 Configuring for Your Coding Agent

Replace the absolute paths and placeholder keys below. Keep credential-bearing settings private and out of version control. The agent host must supply the key to the server; a repository `.env` alone is insufficient.

### Claude Code

Add the server to Claude Code using `claude mcp add`:

```bash
claude mcp add --scope user openrouter-jev-mcp \
  -e OPENROUTER_API_KEY="sk-or-v1-your-key-here" \
  -- /path/to/openrouter-jev-mcp/.venv/bin/python \
     /path/to/openrouter-jev-mcp/src/server.py
```

### OpenAI Codex CLI

Add the server to your `~/.codex/config.toml`:

```toml
[mcp_servers.openrouter_jev_mcp]
command = "/path/to/openrouter-jev-mcp/.venv/bin/python"
args = ["/path/to/openrouter-jev-mcp/src/server.py"]
env = { OPENROUTER_API_KEY = "sk-or-v1-your-key-here" }
```

Launch Codex and use `/mcp` to check that the server starts and exposes all five tools. Tool discovery does not verify provider connectivity.

### Cursor

Add to your Cursor settings (`~/.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "openrouter-jev-mcp": {
      "command": "/path/to/openrouter-jev-mcp/.venv/bin/python",
      "args": ["/path/to/openrouter-jev-mcp/src/server.py"],
      "env": {
        "OPENROUTER_API_KEY": "sk-or-v1-your-key-here"
      }
    }
  }
}
```

---

## 💡 How to Prompt Your Agent

Once configured, use Jev as an additional judgement during development. Your agent or application owns action permissions, thresholds and fallback behaviour; model judgements supplement tests and human review.

### 1. Bug Investigation / Root Cause Triage
> *"Before modifying any code, inspect the failing test trace. Use `jev_classify` to evaluate whether the failure is most likely: `code_defect`, `stale_test`, `flaky_environment`, or `missing_config`. Show me Jev's probabilities before continuing."*

### 2. Pre-Execution Risk Review
> *"Before running a command that deletes or moves files, use `jev_check` to assess whether it could delete persistent project data. Treat the result as advisory and follow the project's existing approval rules regardless of the score. If Jev returns an error, report that no judgement was available."*

### 3. Post-Edit Acceptance Verification
> *"Run the tests and inspect your git diff. Use `jev_evaluate` to score whether the diff satisfies the requirement and whether unexpected files were altered."*

---

## 🐍 Python Library Usage

You can also use the gateway directly in your own Python services. Set `OPENROUTER_API_KEY` first. Calls can raise `JevGatewayError`; handle that as an unavailable judgement. The output comments below are illustrative, not expected test results:

```python
from src.gateway import JevGateway

with JevGateway() as jev:
    # 1. Yes/No Check (Noul)
    result = jev.check(
        state="rm -rf /var/log/*",
        proposition="Does this command delete files outside the current project?"
    )
    print(result["noul"])  # 0.98

    # 2. Categorical Choice (Choice)
    choice = jev.choice(
        state="Connection timeout after 5000ms to redis:6379",
        instructions="What subsystem failed?",
        options={
            "database": "Relational SQL database",
            "cache": "Redis or Memcached key-value store",
            "network": "DNS or proxy routing"
        }
    )
    print(choice["choice"])     # "cache"
    print(choice["confidence"]) # 1.0
```

---

## 🛡️ Validation, Resilience and Privacy

* **Validated answers:** Malformed JSON, missing answers and invalid answer values produce structured errors. Valid structure does not guarantee a correct judgement.
* **Bounded retries:** Up to three attempts for transient HTTP codes (`408, 429, 502, 503, 504`), connection errors and transport timeouts. Exponential backoff starts at 0.25 seconds; `Retry-After` seconds and HTTP-dates are honoured within the remaining request budget.
* **Request bounds:** A 20-second network deadline covers attempts and backoff. Requests and responses are bounded, and at most eight requests may be in flight per gateway instance. Excess calls receive an immediate error.
* **Local diagnostics:** Successful calls log state and answers by default to `$JEV_LOG_DIR` or `~/.local/state/jev-gateway`, with owner-only permissions, a 20 MiB aggregate cap and 24-hour retention. Secret filtering is best effort and cannot detect every sensitive value.
* **Logging exclusions:** RFC 6901 pointers such as `logging_exclusions=["/state/customer"]` omit specified fields from the diagnostic copy. They do **not** remove those fields from the state sent to OpenRouter. Remove confidential information before submitting it.
* **Logging failure handling:** If local diagnostic logging fails, it emits one sanitised warning to `stderr` per logger and preserves decision processing. This does not turn provider errors into approvals.

See [SETUP_GUIDE.md](SETUP_GUIDE.md#limits-retries-and-diagnostics) for detailed limits and privacy controls.

---

## 🧪 Testing

Run the offline test suite with credentials removed and diagnostic logs isolated in a temporary directory. Tests use synthetic keys and fake provider transports; they do not call OpenRouter:

```bash
# Run unit, resilience and stdio subprocess tests
test_logs=$(mktemp -d)
env -u OPENROUTER_API_KEY -u TYPESAFE_API_KEY JEV_LOG_DIR="$test_logs" \
  .venv/bin/python -m unittest discover -s tests -v

# Syntax verification
.venv/bin/python -m compileall -q src tests examples
```

Offline tests do not verify current provider availability. Some restricted execution sandboxes can stall the MCP SDK's worker threads; see the [verification notes](SETUP_GUIDE.md#examples-and-verification). The native TypeSafe SDK example is legacy research material and is not part of the supported installation.

---

## 📄 License

MIT © Chris ([ctmx](https://github.com/ctmx))
