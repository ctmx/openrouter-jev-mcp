"""
src/server.py

General-purpose Model Context Protocol (MCP) Server for Jev AI.
Exposes standard Jev System One decision primitives to any agent (Codex, Claude Code, etc.).
"""

import sys
import os
import json

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from mcp.server.mcpserver import MCPServer
from src.gateway import JevGateway

app = MCPServer(
    name="jev-gateway",
    description="Local Jev AI System One Decision Gateway (via OpenRouter or TypeSafe)"
)

# Initialize gateway (picks up OPENROUTER_API_KEY or TYPESAFE_API_KEY from environment)
gateway = JevGateway()


@app.tool(
    name="jev_check",
    description="Evaluate a boolean proposition (Noul) against state. Returns yes/no probability between 0.0 and 1.0."
)
def jev_check(state: str, proposition: str) -> dict:
    """
    Args:
        state: The context or content to judge (e.g. code snippet, log, user prompt).
        proposition: The assertion to test (e.g. 'Is this action destructive?').
    """
    return gateway.check(state, proposition)


@app.tool(
    name="jev_classify",
    description="Classify state into one label from a closed set of options (Choice). Returns selected label, full probability distribution, and confidence."
)
def jev_classify(state: str, question: str, options: dict) -> dict:
    """
    Args:
        state: The context or content to judge.
        question: The classification question.
        options: Dict mapping label names to descriptions (e.g. {"frontend": "UI/CSS issues", "backend": "API or server issues"}).
    """
    return gateway.choice(state, question, options)


@app.tool(
    name="jev_score",
    description="Rate state against an ordered discrete rubric (Score). Returns expected score index and confidence."
)
def jev_score(state: str, question: str, levels: list) -> dict:
    """
    Args:
        state: The context or content to judge.
        question: The scoring question.
        levels: Ordered list of level descriptions (e.g. ["low: harmless", "medium: cache wipe", "high: database drop"]).
    """
    return gateway.score(state, question, levels)


@app.tool(
    name="jev_evaluate",
    description="General-purpose evaluation: evaluates an arbitrary dictionary of Choice, Score, and Noul questions simultaneously."
)
def jev_evaluate(state: dict, questions: dict) -> dict:
    """
    Args:
        state: Context dict or string.
        questions: Dict of question definitions.
    """
    res = gateway.evaluate(state, questions)
    return {
        "model": res.model,
        "answers": res.answers,
        "usage": res.usage
    }


@app.tool(
    name="jev_health",
    description="Checks Jev gateway connectivity, active provider, and configured model."
)
def jev_health() -> dict:
    return {
        "status": "online",
        "provider": "OpenRouter" if gateway.use_openrouter else "TypeSafe Native",
        "model": gateway.model,
        "key_configured": bool(gateway.openrouter_api_key or gateway.typesafe_api_key)
    }


if __name__ == "__main__":
    app.run()
