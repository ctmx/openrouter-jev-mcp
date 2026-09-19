# Jev AI Local Gateway & MCP Server

A standalone, local gateway and Model Context Protocol (MCP) server for **Jev AI** (TypeSafe AI's System One decision engine).

This repository serves as the shared, central Jev integration layer for any agentic coding project (including Codex CLI, Claude Code, and Cursor).

---

## 1. What This Gateway Provides

Instead of generating free-form text, Jev returns deterministic, typed probabilities in **~70–150 ms** for **$0.042 / million input tokens** ($0 output tokens).

This gateway exposes standard Jev primitives to your agents:
* **`jev_check` (Noul):** Evaluates a yes/no proposition and returns a calibrated probability $P(\text{true}) \in [0.0, 1.0]$.
* **`jev_classify` (Choice):** Categorizes state into one label from a closed set of options with confidence and full distribution.
* **`jev_score` (Score):** Rates state along an ordered rubric (e.g. low/medium/critical).
* **`jev_evaluate`:** Evaluates an arbitrary custom question map simultaneously.
* **`jev_health`:** Verifies gateway connectivity and active model (`~typesafe/jev-latest`).

---

## 2. Quick Start

The virtual environment `.venv` and your API key in `.env` are already configured and verified.

### Run a Test Decision
```bash
source .venv/bin/activate && export $(grep -v '^#' .env | xargs)
python examples/demo_openrouter_decisions.py
```

### Run the MCP Server
```bash
python src/server.py
```

---

## 3. Registering in OpenAI Codex CLI

To make Jev's decision tools available inside Codex:

Add the following block to your `~/.codex/config.toml`:

```toml
[mcp_servers.jev_gateway]
command = "/home/chris/data/projects-ongoing/jev/.venv/bin/python"
args = ["/home/chris/data/projects-ongoing/jev/src/server.py"]
env = { OPENROUTER_API_KEY = "your_openrouter_key" }
```

*(You can also load the key from `.env` directly).*

Once added, launch Codex:
```bash
codex
```
Run `/mcp` inside Codex, and `jev_gateway` will be active with `jev_check`, `jev_classify`, `jev_score`, `jev_evaluate`, and `jev_health`.

---

## 4. Registering in Claude Code

```bash
claude mcp add --scope user jev-gateway \
  -e OPENROUTER_API_KEY="your_openrouter_key" \
  -- /home/chris/data/projects-ongoing/jev/.venv/bin/python \
     /home/chris/data/projects-ongoing/jev/src/server.py
```

---

## 5. Python Library Usage in Other Projects

You can import and use `JevGateway` directly from Python:

```python
import sys
sys.path.insert(0, "/home/chris/data/projects-ongoing/jev")

from src.gateway import JevGateway

jev = JevGateway()

# Yes/No check
result = jev.check(
    state="rm -rf /var/log/*",
    proposition="Does this command delete files outside the repository?"
)
print(result) # {'type': 'noul', 'noul': 0.98}
```

---

## 6. Directory Structure

* [`src/gateway.py`](file:///home/chris/data/projects-ongoing/jev/src/gateway.py) - Reusable Python client for OpenRouter Decisions & TypeSafe APIs.
* [`src/server.py`](file:///home/chris/data/projects-ongoing/jev/src/server.py) - Fast, lightweight MCP server exposing Jev decision tools.
* [`examples/`](file:///home/chris/data/projects-ongoing/jev/examples/) - Runnable standalone decision examples.
* [`prototypes/antirabbithole/`](file:///home/chris/data/projects-ongoing/jev/prototypes/antirabbithole/) - Isolated prototypes and test cases for the 5-signal anti-rabbit-hole supervisor (to be migrated to `codex-antirabbithole`).
* [`RESEARCH_JEV_AI.md`](file:///home/chris/data/projects-ongoing/jev/RESEARCH_JEV_AI.md) - Deep architectural and benchmark research report.
