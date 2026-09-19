# Jev AI Starter & Direction Guard Workspace

This workspace contains research, integration recipes, and runnable implementations for **Jev AI** (TypeSafe AI's System One decision engine), featuring the **Anti-Rabbit-Hole Supervisor (`check_direction`)**.

## Quick Links

- [RESEARCH_JEV_AI.md](file:///home/chris/data/projects-ongoing/jev/RESEARCH_JEV_AI.md) - Deep architectural report, benchmarks, primitives, and MCP analysis.
- [SETUP_GUIDE.md](file:///home/chris/data/projects-ongoing/jev/SETUP_GUIDE.md) - Step-by-step instructions for Claude Code, Codex CLI, and direct APIs.
- [interactive_direction_demo.html](file:///home/chris/data/projects-ongoing/jev/examples/interactive_direction_demo.html) - Single-file interactive HTML prototype with guided walkthroughs and live slider controls.
- [.env.example](file:///home/chris/data/projects-ongoing/jev/.env.example) - Environment variables template.

## Anti-Rabbit-Hole Direction Guard

When coding agents (Astra, Sol, Claude Code, Codex) explore complex tasks, they can get lost in deep, ungrounded tangents. Instead of asking one fuzzy question, the supervisor decomposes tangent evaluation into 5 narrow Jev signals:
1. **Direct Relevance** (`Noul`): Does this address a stated requirement?
2. **Blocking Dependency** (`Noul`): Does evidence show this blocks the primary objective?
3. **Grounded Evidence** (`Score`): Is the concern supported by observed traces vs pure speculation?
4. **Circular Reasoning** (`Noul`): Does this repeat a previously settled question without new data?
5. **Bounded Stopping Check** (`Noul`): Is there a concrete observation that would end this detour?

These signals are combined in deterministic code into three outcomes:
* `CONTINUE`: Grounded and directly relevant / blocking.
* `BOUNDED_PROBE`: Speculative or uncertain, but bounded (allows 1 inspection step).
* `RETURN_TO_MAIN`: Disconnected, circular, or ungrounded speculation.

## Running the Components

### 1. Interactive HTML Prototype
Open [examples/interactive_direction_demo.html](file:///home/chris/data/projects-ongoing/jev/examples/interactive_direction_demo.html) directly in any browser.

### 2. Automated Test Suite
Run the 4 canonical evaluation scenarios (rabbit hole, blocking dependency, 1-step probe, circular retread):
```bash
source .venv/bin/activate
python examples/test_direction_cases.py
```

### 3. Run as an MCP Server
The server exposes the `check_direction` tool to any MCP client:
```bash
python src/mcp_server.py
```
*(See [SETUP_GUIDE.md](file:///home/chris/data/projects-ongoing/jev/SETUP_GUIDE.md) for Claude Code and Codex CLI registration commands).*
