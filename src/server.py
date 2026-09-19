"""Stdio MCP adapter for the validated Jev gateway."""
from __future__ import annotations

import os
import sys
from typing import Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from mcp.server.mcpserver import MCPServer
from src.gateway import JevGateway, JevGatewayError

app = MCPServer(name="jev-gateway", description="Local OpenRouter Jev decision gateway")
gateway = JevGateway()


async def _call(operation: Any) -> dict[str, Any]:
    try:
        return await operation()
    except JevGatewayError as error:
        return error.to_dict()


@app.tool(name="jev_check", description="Evaluate a Noul proposition against string, object, or list state.")
async def jev_check(state: Any, proposition: str, logging_exclusions: list[str] | None = None) -> dict[str, Any]:
    return await _call(lambda: gateway.acheck(state, proposition, logging_exclusions=logging_exclusions))


@app.tool(name="jev_classify", description="Choose one caller-defined label for string, object, or list state.")
async def jev_classify(state: Any, question: Any, options: dict[str, str | None], logging_exclusions: list[str] | None = None) -> dict[str, Any]:
    return await _call(lambda: gateway.achoice(state, question, options, logging_exclusions=logging_exclusions))


@app.tool(name="jev_score", description="Score string, object, or list state against ordered caller-defined levels.")
async def jev_score(state: Any, question: Any, levels: list[str], logging_exclusions: list[str] | None = None) -> dict[str, Any]:
    return await _call(lambda: gateway.ascore(state, question, levels, logging_exclusions=logging_exclusions))


@app.tool(name="jev_evaluate", description="Evaluate a named map of Noul, Choice, and Score questions.")
async def jev_evaluate(state: Any, questions: dict[str, Any], logging_exclusions: list[str] | None = None) -> dict[str, Any]:
    async def evaluate() -> dict[str, Any]:
        result = await gateway.aevaluate(state, questions, logging_exclusions=logging_exclusions)
        return {"model": result.model, "answers": result.answers, "usage": result.usage}
    return await _call(evaluate)


@app.tool(name="jev_health", description="Report OpenRouter configuration readiness; connectivity is unverified unless explicitly probed.")
async def jev_health(verify: bool = False) -> dict[str, Any]:
    async def health() -> dict[str, Any]:
        result = gateway.health()
        if verify and result["ready"]:
            await gateway.acheck("health probe", "Is this a health probe?")
            result["connectivity"] = "verified"
        return result
    return await _call(health)


def run() -> None:
    try:
        gateway.logger.start()
        app.run("stdio")
    finally:
        gateway.close()


if __name__ == "__main__":
    run()
