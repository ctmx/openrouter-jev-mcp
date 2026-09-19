# Step-by-Step Setup Guide: Using Jev AI

This guide shows you how to implement and run **Jev AI** with **Claude Code**, **OpenAI Codex CLI**, and **standalone Python scripts**.

---

## 1. Prerequisites & API Keys

Jev can be accessed through two providers:

### Option A: Official TypeSafe API
1. Sign up / join the developer waitlist at [typesafe.ai](https://typesafe.ai).
2. Generate an API key (`TYPESAFE_API_KEY`).

### Option B: OpenRouter Alpha Decisions API (Immediate Access)
If you do not yet have access to the direct TypeSafe early access program, OpenRouter serves the exact same model (`typesafe/jev-1.13`) via its dedicated decisions endpoint:
1. Generate an API key at [openrouter.ai/keys](https://openrouter.ai/keys).
2. Set `OPENROUTER_API_KEY`.

---

## 2. Setting Up in Claude Code

You have two options for Claude Code:

### Route 1: MCP Server via `blakestone-x/jev-mcp` (Recommended for starting out)

Add the MCP server directly using `uvx`:

```bash
claude mcp add --scope user jev \
  -e TYPESAFE_API_KEY="your_typesafe_key_here" \
  -- uvx --from git+https://github.com/blakestone-x/jev-mcp@v0.2.1 jev-mcp
```

*(Note: If you are using OpenRouter, set `-e TYPESAFE_BASE_URL="https://openrouter.ai/api/alpha" -e TYPESAFE_API_KEY="your_openrouter_key"`)*

Verify in Claude Code:
```bash
claude
```
Inside the session, prompt Claude:
> "Run `jev_health` to check connection, then use `jev_classify` to classify whether this repository is a CLI, web app, or library."

---

### Route 2: `jevwire` Claude Code Plugin (Automatic Lifecyle Hooks)

Brainwires provides a zero-config plugin for Claude Code that runs Jev checks automatically before risky tools run and after command outputs:

```bash
# Inside Claude Code
/plugin marketplace add Brainwires/jevwire
/plugin install jev@brainwires-jevwire
/reload-plugins
```

Then export your key in the shell before launching Claude:
```bash
export TYPESAFE_API_KEY="your_typesafe_key_here"
claude
```

---

## 3. Setting Up in OpenAI Codex CLI

Codex CLI has native MCP support configured via `~/.codex/config.toml`.

### Configure `~/.codex/config.toml`

Open or edit `~/.codex/config.toml` and add:

```toml
[mcp_servers.jev]
command = "uvx"
args = [
  "--from",
  "git+https://github.com/blakestone-x/jev-mcp@v0.2.1",
  "jev-mcp"
]
env = { TYPESAFE_API_KEY = "your_typesafe_key_here" }
```

Alternatively, if you prefer `npx` and `jevwire`:

```toml
[mcp_servers.jev]
command = "npx"
args = ["-y", "jevwire"]
env = { TYPESAFE_API_KEY = "your_typesafe_key_here" }
```

### Testing in Codex

Launch Codex:
```bash
codex
```
Type:
```text
/mcp
```
You will see `jev` listed as an active server with its tools (`jev_ask`, `jev_classify`, `jev_score`, `jev_check`, etc.).

---

## 4. Setting Up Your Custom `check_direction` Advisory Supervisor

This repository includes a pre-built MCP server implementing the **5-question anti-rabbit-hole supervisor**:

### Registering in Claude Code:
```bash
claude mcp add --scope user direction-guard \
  -e TYPESAFE_API_KEY="your_key" \
  -- /home/chris/data/projects-ongoing/jev/.venv/bin/python \
     /home/chris/data/projects-ongoing/jev/src/mcp_server.py
```

### Registering in Codex CLI (`~/.codex/config.toml`):
```toml
[mcp_servers.direction_guard]
command = "/home/chris/data/projects-ongoing/jev/.venv/bin/python"
args = ["/home/chris/data/projects-ongoing/jev/src/mcp_server.py"]
env = { TYPESAFE_API_KEY = "your_key" }
```

### Prompting Astra / Sol / Claude Code to use it:
> "Before exploring any detour or tangent away from the primary task, call `check_direction` with the main objective, your proposed investigation, and the evidence observed. Obey its recommendation."

---

## 5. Local Python Sandbox (Testing Without an Agent)

This directory already includes a configured virtual environment (`.venv`) with `typesafe-sdk`.

### 1. Set your environment variable:
```bash
cp .env.example .env
# Edit .env and enter your TYPESAFE_API_KEY or OPENROUTER_API_KEY
```

### 2. Run the provided demo script:
```bash
# Using direct TypeSafe SDK:
source .venv/bin/activate
python examples/demo_typesafe_sdk.py

# Or using OpenRouter Decisions API:
python examples/demo_openrouter_decisions.py
```
