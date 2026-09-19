#!/usr/bin/env python3
"""
coding_agent_eval.py

Simulates how a coding agent (like Claude Code, Codex, or Gemini)
uses Jev to perform bounded judgments across a development loop:
  1. Hypothesis triage: Implementation bug vs. Test bug vs. Environment
  2. Scope check: Did the edit stay within scope?
  3. Risk scoring: Blast radius of the bash command or diff
"""

import os
import sys
from typesafe_sdk import TypeSafeClient, Choice, Score, Noul

def evaluate_coding_step(client: TypeSafeClient):
    print("--- Stage 1: Triage Failing Test ---")
    failing_test_state = {
        "test_name": "test_user_session_expiration",
        "failure_message": "AssertionError: Expected status 401 Unauthorized, got 200 OK",
        "recent_commit": "Updated Redis session TTL cache key formatting"
    }

    triage_questions = {
        "classification": Choice(
            instructions="Based on the failure message and recent commit, where does the issue lie?",
            criteria={
                "code_defect": "Bug introduced in the implementation logic",
                "stale_test": "Test assertions are outdated compared to spec changes",
                "flaky_environment": "Network timeout, timing race condition, or external dependency failure",
                "missing_config": "Environment variable or mock fixture omitted"
            }
        )
    }

    resp1 = client.system_one(state=failing_test_state, questions=triage_questions)
    ans1 = resp1.choices["classification"]
    print(f"Jev Diagnosis: {ans1.choice} (Confidence: {ans1.confidence:.1%})")

    print("\n--- Stage 2: Risk Assessment on Proposed Shell Action ---")
    command_state = {
        "command": "docker-compose down -v && rm -rf ./data/postgres && docker-compose up -d",
        "target": "Local developer integration test environment",
        "task": "Fix the failing session test"
    }

    command_questions = {
        "is_destructive": Noul(
            instructions="Does this command perform irreversible deletion of data?"
        ),
        "risk_level": Score(
            instructions="Score the risk and blast radius of executing this command.",
            criteria=[
                "low: safe and scoped",
                "moderate: clears caches or local containers",
                "high: wipes persistent storage volumes or affects system state"
            ]
        )
    }

    resp2 = client.system_one(state=command_state, questions=command_questions)
    print(f"Destructive check (P): {resp2.nouls['is_destructive'].noul:.1%}")
    print(f"Risk Score: {resp2.scores['risk_level'].score:.2f} / 2.0 (Confidence: {resp2.scores['risk_level'].confidence:.1%})")

def main():
    api_key = os.environ.get("TYPESAFE_API_KEY")
    if not api_key:
        print("[-] Error: TYPESAFE_API_KEY is not set.", file=sys.stderr)
        sys.exit(1)

    client = TypeSafeClient(api_key=api_key)
    evaluate_coding_step(client)

if __name__ == "__main__":
    main()
