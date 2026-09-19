"""
src/direction_guard.py

Anti-Rabbit-Hole Supervisor / Tangent Checker for Coding Agents (Astra, Sol, Codex, Claude Code).
Uses TypeSafe Jev (or OpenRouter Decisions API) to decompose tangent evaluation
into 5 narrow questions, then combines the signals in deterministic code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional

# Decision outcomes
DecisionType = Literal["CONTINUE", "BOUNDED_PROBE", "RETURN_TO_MAIN"]


@dataclass
class DirectionSignals:
    direct_relevance: float         # P(True): Addresses stated requirement
    blocking_dependency: float      # P(True): Subsystem blocks main objective
    grounded_evidence: float        # Score [0.0 - 2.0]: 0=speculative, 1=weak, 2=grounded
    circular_reasoning: float       # P(True): Repeats settled question without new data
    bounded_stopping_condition: float  # P(True): Concrete observation would end investigation


@dataclass
class DirectionEvaluation:
    decision: DecisionType
    confidence: float
    rationale: str
    signals: DirectionSignals
    recommended_action: str


class DirectionPolicy:
    """
    Combines the 5 narrow Jev signals into a deterministic policy decision.
    Principle: Uncertainty preserves the model's freedom to investigate
    via BOUNDED_PROBE rather than prematurely blocking it.
    """

    @staticmethod
    def evaluate(s: DirectionSignals) -> DirectionEvaluation:
        # Rule 1: Circular reasoning (retreading settled questions) is an immediate veto.
        if s.circular_reasoning >= 0.65:
            return DirectionEvaluation(
                decision="RETURN_TO_MAIN",
                confidence=s.circular_reasoning,
                rationale="Proposed investigation retreads an already settled question without introducing new contradictory evidence.",
                signals=s,
                recommended_action="Return immediately to the primary objective. Do not re-investigate settled decisions."
            )

        # Rule 2: Completely disconnected from the objective (neither relevant nor a blocking dependency).
        if s.direct_relevance < 0.30 and s.blocking_dependency < 0.30:
            conf = 1.0 - max(s.direct_relevance, s.blocking_dependency)
            return DirectionEvaluation(
                decision="RETURN_TO_MAIN",
                confidence=conf,
                rationale="Investigation has no demonstrable connection to the primary objective and no evidence of being a blocking prerequisite.",
                signals=s,
                recommended_action="Abandon this detour. Refocus on the direct symptoms and requirements of the main task."
            )

        # Rule 3: Pure ungrounded speculation with no bounded check.
        if s.grounded_evidence < 0.70 and s.bounded_stopping_condition < 0.40:
            return DirectionEvaluation(
                decision="RETURN_TO_MAIN",
                confidence=0.85,
                rationale="Investigation is speculative with no observed failure traces and no concrete stopping observation (unbounded rabbit hole risk).",
                signals=s,
                recommended_action="Do not pursue open-ended speculation. Seek concrete logs, tests, or reproducible traces first."
            )

        # Rule 4: Clear Green Light (Grounded relevance or blocking dependency with clear stopping condition).
        is_relevant_or_blocking = (s.direct_relevance >= 0.65 or s.blocking_dependency >= 0.65)
        if is_relevant_or_blocking and s.grounded_evidence >= 1.20 and s.bounded_stopping_condition >= 0.50:
            conf = min(0.95, (max(s.direct_relevance, s.blocking_dependency) + s.bounded_stopping_condition) / 2.0)
            return DirectionEvaluation(
                decision="CONTINUE",
                confidence=conf,
                rationale="Investigation is well-grounded, directly relevant or blocking, and has a clear bounded completion condition.",
                signals=s,
                recommended_action="Proceed with the investigation towards the concrete stopping condition."
            )

        # Rule 5: Default preservation of exploratory freedom: Bounded probe.
        # Catches speculative hypotheses that nevertheless have a clear 1-step test,
        # or plausible dependencies with moderate evidence.
        return DirectionEvaluation(
            decision="BOUNDED_PROBE",
            confidence=0.75,
            rationale="Investigation carries potential relevance but is unproven or speculative. Preserving exploratory freedom with a 1-step bound.",
            signals=s,
            recommended_action="Execute exactly ONE bounded inspection (e.g. read 1 specific file or run 1 targeted probe). If no contradiction or proof is found, return to main task."
        )


class DirectionGuard:
    """
    Client for assessing proposed tangents using Jev.
    """

    def __init__(
        self,
        typesafe_api_key: Optional[str] = None,
        openrouter_api_key: Optional[str] = None,
        use_openrouter: bool = False
    ):
        self.typesafe_api_key = typesafe_api_key or os.environ.get("TYPESAFE_API_KEY")
        self.openrouter_api_key = openrouter_api_key or os.environ.get("OPENROUTER_API_KEY")
        self.use_openrouter = use_openrouter or (not self.typesafe_api_key and bool(self.openrouter_api_key))

    @staticmethod
    def build_questions() -> Dict[str, Any]:
        """The 5 narrow Jev questions."""
        try:
            from typesafe_sdk import Choice, Score, Noul
            return {
                "direct_relevance": Noul(
                    instructions="Does this proposed investigation directly address a stated requirement of the main objective?",
                    criteria={
                        "true": "Directly explores or modifies code required by the primary goal.",
                        "false": "Focuses on secondary behavior, tangential refactoring, or a separate subsystem."
                    }
                ),
                "blocking_dependency": Noul(
                    instructions="Does the supplied evidence demonstrate that this subsystem or issue is a prerequisite or blocking dependency for the main objective?",
                    criteria={
                        "true": "The main objective cannot be completed or diagnosed without resolving this blocker.",
                        "false": "The main objective does not depend on this subsystem, or the dependency is purely speculative."
                    }
                ),
                "grounded_evidence": Score(
                    instructions="How well is the concern supported by concrete observed failure traces, contradictions, or direct symptoms in the supplied evidence?",
                    criteria=[
                        "speculative: hypothetical concern with no observed failure, log, or symptom in evidence",
                        "weak: indirect correlation or anecdotal suspicion without causal link",
                        "grounded: directly backed by a reproducer, log trace, assertion failure, or demonstrable code path"
                    ]
                ),
                "circular_reasoning": Noul(
                    instructions="Does this proposed investigation repeat a question that was already settled in previously settled decisions without introducing new contradictory evidence?",
                    criteria={
                        "true": "Retreads an already investigated and dismissed hypothesis without new data.",
                        "false": "Explores a fresh hypothesis or re-opens a settled question due to new conflicting evidence."
                    }
                ),
                "bounded_stopping_condition": Noul(
                    instructions="Is there a concrete, bounded observation or single test that would definitively prove or disprove this hypothesis?",
                    criteria={
                        "true": "Has a clear stopping condition (e.g. check a specific log line or run one specific test).",
                        "false": "Open-ended, subjective exploration or unbounded audit."
                    }
                )
            }
        except ImportError:
            # Wire JSON shape fallback if typesafe_sdk not imported
            return {
                "direct_relevance": {"type": "noul", "instructions": "Does this investigation address a stated requirement?"},
                "blocking_dependency": {"type": "noul", "instructions": "Does supplied evidence identify a blocking dependency?"},
                "grounded_evidence": {"type": "score", "instructions": "Is concern supported by observed failure vs speculation?", "criteria": ["speculative", "weak", "grounded"]},
                "circular_reasoning": {"type": "noul", "instructions": "Does this repeat a settled question without new evidence?"},
                "bounded_stopping_condition": {"type": "noul", "instructions": "Is there a concrete observation that would end this investigation?"}
            }

    def check_direction(
        self,
        main_objective: str,
        proposed_investigation: str,
        evidence: str,
        settled_decisions: str = "None"
    ) -> DirectionEvaluation:
        """
        Evaluates a proposed investigation using Jev and applies the DirectionPolicy.
        """
        state = {
            "main_objective": main_objective,
            "proposed_investigation": proposed_investigation,
            "evidence": evidence,
            "settled_decisions": settled_decisions
        }

        # Route 1: Live TypeSafe SDK
        if self.typesafe_api_key and not self.use_openrouter:
            from typesafe_sdk import TypeSafeClient
            client = TypeSafeClient(api_key=self.typesafe_api_key)
            questions = self.build_questions()
            resp = client.system_one(state=state, questions=questions)
            
            signals = DirectionSignals(
                direct_relevance=resp.nouls["direct_relevance"].noul,
                blocking_dependency=resp.nouls["blocking_dependency"].noul,
                grounded_evidence=resp.scores["grounded_evidence"].score,
                circular_reasoning=resp.nouls["circular_reasoning"].noul,
                bounded_stopping_condition=resp.nouls["bounded_stopping_condition"].noul
            )
            return DirectionPolicy.evaluate(signals)

        # Route 2: OpenRouter Decisions API
        if self.openrouter_api_key and self.use_openrouter:
            import httpx
            url = "https://openrouter.ai/api/alpha/decisions"
            headers = {"Authorization": f"Bearer {self.openrouter_api_key}", "Content-Type": "application/json"}
            payload = {
                "model": "typesafe/jev-1.13",
                "state": state,
                "questions": self.build_questions()
            }
            res = httpx.post(url, headers=headers, json=payload, timeout=15.0)
            res.raise_for_status()
            data = res.json()
            ans = data.get("answers", {})
            signals = DirectionSignals(
                direct_relevance=ans.get("direct_relevance", {}).get("noul", 0.5),
                blocking_dependency=ans.get("blocking_dependency", {}).get("noul", 0.5),
                grounded_evidence=ans.get("grounded_evidence", {}).get("score", 1.0),
                circular_reasoning=ans.get("circular_reasoning", {}).get("noul", 0.1),
                bounded_stopping_condition=ans.get("bounded_stopping_condition", {}).get("noul", 0.5)
            )
            return DirectionPolicy.evaluate(signals)

        # Route 3: Offline Sandbox / Mock Simulation Mode (when neither key is set)
        return self._simulate_mock_evaluation(state)

    def _simulate_mock_evaluation(self, state: Dict[str, Any]) -> DirectionEvaluation:
        """
        A deterministic mock simulation for offline testing of cases without API keys.
        """
        prop = state["proposed_investigation"].lower()
        obj = state["main_objective"].lower()
        ev = state["evidence"].lower()
        dec = state["settled_decisions"].lower()

        # Check circular
        is_circular = any(word in dec for word in prop.split() if len(word) > 4) and ("already" in dec or "settled" in dec or "ruled out" in dec)
        
        # Check relevance & blocking
        has_common_domain = any(term in prop for term in ["login", "auth", "token", "timeout", "latency", "redis"])
        is_payment_in_login = "payment" in prop and "login" in obj and ("no payment" in ev or "payment" not in ev)
        
        if is_circular:
            s = DirectionSignals(0.2, 0.1, 0.4, 0.92, 0.4)
        elif is_payment_in_login:
            s = DirectionSignals(0.08, 0.05, 0.15, 0.02, 0.25)
        elif "redis" in prop and "redis" in ev:
            s = DirectionSignals(0.85, 0.91, 1.85, 0.01, 0.88)
        elif "clock" in prop or "drift" in prop:
            s = DirectionSignals(0.45, 0.60, 0.55, 0.05, 0.82)
        else:
            s = DirectionSignals(0.50, 0.50, 1.00, 0.05, 0.50)

        return DirectionPolicy.evaluate(s)
