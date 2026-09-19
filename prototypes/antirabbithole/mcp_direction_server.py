"""
src/mcp_server.py

Model Context Protocol (MCP) Server exposing the Jev DirectionGuard.
Provides the `check_direction` advisory tool to coding agents (Astra, Sol, Codex, Claude Code).
"""

import sys
import os

# Ensure package path is resolvable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from mcp.server.mcpserver import MCPServer
from src.direction_guard import DirectionGuard

app = MCPServer(
    name="direction-guard",
    description="Anti-rabbit-hole advisory supervisor for coding agents using TypeSafe Jev"
)

# Initialize DirectionGuard (loads TYPESAFE_API_KEY or OPENROUTER_API_KEY if available)
guard = DirectionGuard()

@app.tool(
    name="check_direction",
    description="Advisory direction check before embarking on an investigative tangent or detour. Returns CONTINUE, BOUNDED_PROBE, or RETURN_TO_MAIN."
)
def check_direction(
    main_objective: str,
    proposed_investigation: str,
    evidence: str,
    settled_decisions: str = "None"
) -> dict:
    """
    Evaluates whether a proposed investigative detour is justified or a rabbit hole.
    
    Args:
        main_objective: The user's primary goal or high-level issue being resolved.
        proposed_investigation: The specific tangent or hypothesis the agent wants to explore.
        evidence: Concrete observed logs, traces, or reproduction symptoms seen so far.
        settled_decisions: Relevant past hypotheses that were already tested and ruled out.
    """
    eval_result = guard.check_direction(
        main_objective=main_objective,
        proposed_investigation=proposed_investigation,
        evidence=evidence,
        settled_decisions=settled_decisions
    )

    sig = eval_result.signals
    return {
        "decision": eval_result.decision,
        "confidence": round(eval_result.confidence, 3),
        "rationale": eval_result.rationale,
        "recommended_action": eval_result.recommended_action,
        "signals": {
            "direct_relevance": round(sig.direct_relevance, 3),
            "blocking_dependency": round(sig.blocking_dependency, 3),
            "grounded_evidence_score": round(sig.grounded_evidence, 3),
            "circular_reasoning": round(sig.circular_reasoning, 3),
            "bounded_stopping_condition": round(sig.bounded_stopping_condition, 3)
        }
    }

if __name__ == "__main__":
    app.run()
