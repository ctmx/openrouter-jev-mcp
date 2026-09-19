"""Run the real stdio server with a deterministic in-process OpenRouter transport.

This is deliberately a separate process: the integration test must exercise
``app.run(\"stdio\")`` rather than an in-memory MCP server.
"""
from __future__ import annotations

import json
import asyncio

import httpx


_attempts: dict[str, int] = {}


async def _response(request: httpx.Request) -> httpx.Response:
    """Return the documented Decisions shape without making a network request."""
    try:
        payload = json.loads(request.content)
    except (TypeError, ValueError):
        payload = {}

    if payload.get("state") == "provider-error":
        return httpx.Response(503, json={"error": "synthetic provider outage"})
    if payload.get("state") == "retry-once":
        attempt = _attempts.get("retry-once", 0)
        _attempts["retry-once"] = attempt + 1
        if not attempt:
            return httpx.Response(503, json={"error": "synthetic transient outage"})
    if payload.get("state") == "timeout":
        await asyncio.sleep(0.05)

    answers = {}
    for name, question in payload.get("questions", {}).items():
        kind = question.get("type")
        criteria = question.get("criteria", ())
        if kind == "noul":
            answers[name] = {"type": "noul", "noul": 0.9 if "SENTINEL" in repr(payload.get("state")) else 0.75}
        elif kind == "choice":
            labels = list(criteria)
            label = labels[0]
            answers[name] = {
                "type": "choice",
                "choice": label,
                "probabilities": {item: 1 / len(labels) for item in labels},
                "confidence": 1.0,
            }
        elif kind == "score":
            answers[name] = {
                "type": "score",
                "score": 0.5,
                "legend": {str(index): level for index, level in enumerate(criteria)},
                "probabilities": {"0": 0.5, "1": 0.5},
                "confidence": 1.0,
            }
    return httpx.Response(
        200,
        json={
            "model": "synthetic/jev",
            "answers": answers,
            "usage": {"input_tokens": 3, "output_tokens": 1},
        },
    )


from src import server  # noqa: E402
from src.gateway import JevGateway  # noqa: E402


# Replace only the launcher process's global gateway.  The production server
# retains its normal OpenRouter transport.
server.gateway = JevGateway(
    http_transport=httpx.MockTransport(_response),
    timeout_seconds=0.02,
    max_attempts=2,
    retry_backoff_seconds=0.001,
)
app = server.app


if __name__ == "__main__":
    server.run()
