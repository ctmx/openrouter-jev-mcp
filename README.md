# openrouter-jev-mcp

[![MCP Standard](https://img.shields.io/badge/MCP-2024--11--05-blue.svg)](https://modelcontextprotocol.io/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-brightgreen.svg)](https://www.python.org/)
[![Provider: OpenRouter](https://img.shields.io/badge/Provider-OpenRouter-purple.svg)](https://openrouter.ai/)
[![Model: Jev Latest](https://img.shields.io/badge/Model-~typesafe%2Fjev--latest-orange.svg)](https://openrouter.ai/~typesafe/jev-latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> **High-speed, calibrated "System One" decision gateway and Model Context Protocol (MCP) server for TypeSafe's Jev model — powered instantly via OpenRouter.**

---

## ⚡ What is This?

Large Language Models (like Claude 3.7, GPT-4o, or Gemini) are **"System Two"** thinkers: deliberative, generative, and sequential. However, coding agents repeatedly encounter dozens of small, bounded questions:

```text
               "Is this bug most likely:
      code_defect / stale_test / network_timeout?"
                          │
                          ▼
                   ┌──────────────┐
                   │   Jev AI     │  System One: 80–150ms
                   │  Judge via   │  $0.042 / 1M tokens ($0 output)
                   │  OpenRouter  │  Full confidence & probabilities
                   └──────┬───────┘
                          │
          network_timeout (p = 0.94)
                          │
                          ▼
            Agent acts with high confidence
```

**TypeSafe AI's Jev** is a purpose-built discriminative model designed specifically for software decisions. It does not generate text or autoregressively stream tokens; it outputs **strictly typed, probabilistic decisions** in a single parallel pass.

### Why OpenRouter?
Direct native TypeSafe access is currently behind a private developer waitlist. **`openrouter-jev-mcp`** connects to OpenRouter's dedicated Decisions API (`https://openrouter.ai/api/alpha/decisions` with `~typesafe/jev-latest`), providing **immediate, zero-waitlist access** to Jev with your standard OpenRouter key.

---

## 🛠️ MCP Tools Exposed

This server runs over standard `stdio` and implements the MCP specification:

| Tool | Jev Primitive | Use Case | Return Value |
| :--- | :--- | :--- | :--- |
| `jev_check` | **Noul** | Yes / No propositions | Calibrated probability $P(\text{true}) \in [0.0, 1.0]$. |
| `jev_classify` | **Choice** | Categorizing state into a closed set of labels | Chosen label, full probability distribution, and confidence ($0.0–1.0$). |
| `jev_score` | **Score** | Placing state along an ordered discrete rubric | Expected score index and confidence score. |
| `jev_evaluate` | **Multi-Question** | Evaluating an arbitrary dictionary of Choice, Score, and Noul questions simultaneously in one parallel pass | Dictionary of typed answers and token usage. |
| `jev_health` | **Diagnostics** | Verification of API readiness and provider connectivity | Server health status, configured model, and connectivity verification. |

---

## 🚀 Quick Start

### 1. Prerequisites
* Python 3.10+ (or [uv](https://docs.astral.sh/uv/))
* An [OpenRouter API Key](https://openrouter.ai/keys)

### 2. Installation & Setup
Clone the repository and install dependencies:

```bash
git clone https://github.com/ctmx/openrouter-jev-mcp.git
cd openrouter-jev-mcp

# Using uv (recommended):
uv venv .venv
source .venv/bin/activate
uv pip install -e .

# Or standard pip:
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Copy the environment template and set your key:
```bash
cp .env.example .env
# Edit .env with your actual key:
# OPENROUTER_API_KEY=sk-or-v1-...
chmod 600 .env
```

### 3. Verify Live Connectivity
Run the included verification script:
```bash
export $(grep -v '^#' .env | xargs)
python examples/demo_openrouter_decisions.py
```

---

## 🤖 Configuring for Your Coding Agent

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

Launch Codex and type `/mcp` — `openrouter_jev_mcp` will be active with all five tools.

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

Once configured, instruct your agent to use Jev as an objective judge during development:

### 1. Bug Investigation / Root Cause Triage
> *"Before modifying any code, inspect the failing test trace. Use `jev_classify` to evaluate whether the failure is most likely: `code_defect`, `stale_test`, `flaky_environment`, or `missing_config`. Show me Jev's probabilities before continuing."*

### 2. Pre-Execution Safety Gating
> *"Before running any shell command that deletes or moves files, invoke `jev_check` with the proposition: 'Does this command perform irreversible deletion of persistent project data?'. If probability > 0.70, stop and ask for human confirmation."*

### 3. Post-Edit Acceptance Verification
> *"Run the tests and inspect your git diff. Use `jev_evaluate` to score whether the diff satisfies the requirement and whether unexpected files were altered."*

---

## 🐍 Python Library Usage

You can also use the gateway directly in your own Python services:

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

## 🛡️ Hardening & Enterprise Safety Features

* **Zero-Hallucination Schemas:** Jev cannot hallucinate prose, markdown fences, or malformed JSON. The response is strictly bounded by the request schema.
* **Resilience & Retry Policies:** Automatic exponential backoff with jitter on transient HTTP codes (`408, 429, 502, 503, 504`), parsing provider `Retry-After` headers (both integer seconds and HTTP-dates).
* **Hard Deadlines & In-Flight Throttling:** Strict global deadline per call (`timeout_seconds = 20.0`), bounded response streams, and semaphore concurrency limits (`max_in_flight = 8`).
* **Privacy & Secret Redaction:** Diagnostics logger automatically masks `OPENROUTER_API_KEY`, Bearer tokens, and credential patterns.
* **Granular Exclusions:** Supports RFC 6901 JSON pointer exclusions (`logging_exclusions=["/state/secret_token"]`) ensuring proprietary customer data never reaches local diagnostic logs.
* **Fail-Open Design:** If local diagnostic logging fails (e.g. read-only disk), it emits a single warning to `stderr` and preserves normal decision processing.

---

## 🧪 Testing

Run the comprehensive offline test suite (no credentials or network required):

```bash
# Run all 51 unit, resilience, and stdio subprocess tests
.venv/bin/python -m unittest discover -s tests -v

# Syntax verification
.venv/bin/python -m compileall -q src tests examples
```

---

## 📄 License

MIT © Chris ([ctmx](https://github.com/ctmx))
