#!/usr/bin/env python3
"""
examples/test_direction_cases.py

Exercises the DirectionGuard against 4 canonical scenarios:
  Case 1: Wasted Rabbit Hole (payment investigation during login timeout) -> RETURN_TO_MAIN
  Case 2: Grounded Necessary Depth (Redis connection timeout blocking auth) -> CONTINUE
  Case 3: Speculative with Bounded Test (clock drift hypothesis with 1 check) -> BOUNDED_PROBE
  Case 4: Circular Retread (retesting an already settled hypothesis) -> RETURN_TO_MAIN
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.direction_guard import DirectionGuard

def run_tests():
    guard = DirectionGuard()
    print("=" * 70)
    print(" DIRECTION GUARD: ANTI-RABBIT-HOLE SUPERVISOR TEST CASES")
    print("=" * 70)

    test_cases = [
        {
            "name": "Case 1: Wasted Rabbit Hole (Disconnected Tangent)",
            "main_objective": "Fix a login timeout on the customer portal.",
            "proposed_investigation": "Investigate whether upstream retries can duplicate a credit card payment transaction.",
            "evidence": "Observed 504 Gateway Timeout on POST /api/v1/auth/login. No payment calls exist in login stack trace.",
            "settled_decisions": "Network ingress proxy is healthy.",
            "expected": "RETURN_TO_MAIN"
        },
        {
            "name": "Case 2: Grounded Necessary Depth (Blocking Dependency)",
            "main_objective": "Fix a login timeout on the customer portal.",
            "proposed_investigation": "Investigate Redis connection pool exhaustion during user session token verification.",
            "evidence": "Log trace shows: 'redis.exceptions.ConnectionError: Timeout waiting for connection pool after 5000ms' during POST /api/v1/auth/login.",
            "settled_decisions": "Network ingress proxy is healthy.",
            "expected": "CONTINUE"
        },
        {
            "name": "Case 3: Speculative Hypothesis with Bounded 1-Step Probe",
            "main_objective": "Fix a login timeout on the customer portal.",
            "proposed_investigation": "Check if NTP clock drift between auth server and JWT issuer invalidates nbf/exp claims immediately.",
            "evidence": "No explicit NTP error in logs yet, but logins fail intermittently across 3 different nodes.",
            "settled_decisions": "Network ingress proxy is healthy.",
            "expected": "BOUNDED_PROBE"
        },
        {
            "name": "Case 4: Circular Retread (Settled Decision Re-opened)",
            "main_objective": "Fix a login timeout on the customer portal.",
            "proposed_investigation": "Inspect ingress nginx keepalive and timeout headers again.",
            "evidence": "Intermittent timeouts continue.",
            "settled_decisions": "Ingress nginx keepalive and timeout headers were already inspected, verified correct, and ruled out in step 2.",
            "expected": "RETURN_TO_MAIN"
        }
    ]

    for tc in test_cases:
        print(f"\n▶ Testing: {tc['name']}")
        print(f"  Objective:  {tc['main_objective']}")
        print(f"  Detour:     {tc['proposed_investigation']}")
        
        result = guard.check_direction(
            main_objective=tc["main_objective"],
            proposed_investigation=tc["proposed_investigation"],
            evidence=tc["evidence"],
            settled_decisions=tc["settled_decisions"]
        )

        sig = result.signals
        print(f"  [Signals] Relevance={sig.direct_relevance:.2f}, Blocking={sig.blocking_dependency:.2f}, "
              f"Evidence={sig.grounded_evidence:.2f}/2, Circular={sig.circular_reasoning:.2f}, Bounded={sig.bounded_stopping_condition:.2f}")
        
        status = "PASSED" if result.decision == tc["expected"] else "FAILED"
        print(f"  Decision:   {result.decision} ({status}) | Confidence: {result.confidence:.1%}")
        print(f"  Rationale:  {result.rationale}")
        print(f"  Action:     {result.recommended_action}")

    print("\n" + "=" * 70)
    print("All test cases evaluated successfully.")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()
