#!/usr/bin/env python3
"""
demo_typesafe_sdk.py

Demonstrates how to interact with TypeSafe AI's Jev model using the official typesafe-sdk.
Evaluates:
  1. Choice: Root cause hypothesis classification
  2. Score: Risk assessment rubric
  3. Noul: Requirement satisfaction proposition (Yes/No with confidence)
"""

import os
import sys
from typesafe_sdk import TypeSafeClient, Choice, Score, Noul

def main():
    api_key = os.environ.get("TYPESAFE_API_KEY")
    if not api_key:
        print("[-] Error: TYPESAFE_API_KEY environment variable is not set.", file=sys.stderr)
        print("    Export it with: export TYPESAFE_API_KEY='your_api_key'", file=sys.stderr)
        print("    Or set it in a .env file.", file=sys.stderr)
        sys.exit(1)

    print("[+] Connecting to TypeSafe Jev...")
    client = TypeSafeClient(api_key=api_key)

    # State: Real-world scenario in software development
    state = {
        "git_diff": """
--- a/auth/jwt.py
+++ b/auth/jwt.py
@@ -14,3 +14,5 @@ def verify_token(token: str):
-    return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
+    if os.environ.get("DEBUG") == "1":
+        return {"sub": "admin", "role": "superuser"}
+    return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
""",
        "context": "Feature branch attempting to simplify local test fixtures.",
        "author_intent": "Make it easier to run local mock tests without signing tokens."
    }

    # Questions: 3 primitives
    questions = {
        # 1. Choice: Pick one category from a closed set
        "root_cause_type": Choice(
            instructions="What kind of change is this code modification?",
            criteria={
                "security_backdoor": "Bypasses authentication or introduces a backdoor vulnerability.",
                "safe_test_mock": "Isolated mocking logic only executed in isolated test environments.",
                "refactoring": "Internal structural cleanup with no functional logic divergence.",
                "bug_fix": "Fixes an existing defect in token decoding."
            }
        ),

        # 2. Score: Ordered rubric (low to critical)
        "security_risk": Score(
            instructions="Assess the security impact of this diff if merged to production.",
            criteria=[
                "negligible: no risk",
                "low: test file only",
                "medium: potential configuration leak",
                "critical: hardcoded admin bypass reachable in production if DEBUG=1"
            ]
        ),

        # 3. Noul: Bernoulli proposition (True / False probability)
        "ready_for_production": Noul(
            instructions="Is this change safe to deploy directly to a production environment?"
        )
    }

    print("[*] Submitting state and questions to Jev (System One evaluation)...")
    response = client.system_one(state=state, questions=questions)

    print("\n" + "=" * 50)
    print(" JEV DECISION ENGINE RESULTS")
    print("=" * 50)

    # 1. Choice Result
    choice_ans = response.choices["root_cause_type"]
    print(f"\n[1] Choice: root_cause_type")
    print(f"    Selected:   {choice_ans.choice}")
    print(f"    Confidence: {choice_ans.confidence:.2%}")
    print(f"    Probabilities:")
    for label, prob in choice_ans.probabilities.items():
        bar = "█" * int(prob * 20)
        print(f"      - {label:<22} {prob:.2%} | {bar}")

    # 2. Score Result
    score_ans = response.scores["security_risk"]
    print(f"\n[2] Score: security_risk")
    print(f"    Score Index: {score_ans.score:.2f} (Scale: 0 - 3)")
    print(f"    Confidence:  {score_ans.confidence:.2%}")

    # 3. Noul Result
    noul_ans = response.nouls["ready_for_production"]
    print(f"\n[3] Noul: ready_for_production")
    print(f"    P(True):     {noul_ans.noul:.2%}")
    verdict = "APPROVED" if noul_ans.noul > 0.8 else ("REJECTED" if noul_ans.noul < 0.2 else "NEEDS HUMAN REVIEW")
    print(f"    Gate Status: {verdict}")

    print("\n" + "=" * 50)
    print(f"Tokens Used: Input={response.usage.input_tokens}, Output={response.usage.output_tokens}")
    print("=" * 50)

if __name__ == "__main__":
    main()
