#!/usr/bin/env python3
import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.gateway import JevGateway, JevGatewayError

def evaluate_coding_step(gateway: JevGateway) -> None:
    print("--- Stage 1: Triage Failing Test ---")
    failing_test_state = {
        "test_name": "test_user_session_expiration",
        "failure_message": "AssertionError: Expected status 401 Unauthorized, got 200 OK",
        "recent_commit": "Updated Redis session TTL cache key formatting"
    }

    triage_questions = {
        "classification": {
            "type": "choice",
            "instructions": "Based on the failure message and recent commit, where does the issue lie?",
            "criteria": {
                "code_defect": "Bug introduced in the implementation logic",
                "stale_test": "Test assertions are outdated compared to spec changes",
                "flaky_environment": "Network timeout, timing race condition, or external dependency failure",
                "missing_config": "Environment variable or mock fixture omitted",
            },
        }
    }

    resp1 = gateway.evaluate(failing_test_state, triage_questions)
    print(json.dumps(resp1.answers, indent=2))

    print("\n--- Stage 2: Risk Assessment on Proposed Shell Action ---")
    command_state = {
        "command": "docker-compose down -v && rm -rf ./data/postgres && docker-compose up -d",
        "target": "Local developer integration test environment",
        "task": "Fix the failing session test"
    }

    command_questions = {
        "is_destructive": {
            "type": "noul",
            "instructions": "Does this command perform irreversible deletion of data?",
        },
        "risk_level": {
            "type": "score",
            "instructions": "Score the risk and blast radius of executing this command.",
            "criteria": [
                "low: safe and scoped",
                "moderate: clears caches or local containers",
                "high: wipes persistent storage volumes or affects system state",
            ],
        },
    }

    resp2 = gateway.evaluate(command_state, command_questions)
    print(json.dumps(resp2.answers, indent=2))

def main():
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("OPENROUTER_API_KEY is not set.", file=sys.stderr)
        sys.exit(1)

    gateway = JevGateway(openrouter_api_key=api_key)
    try:
        evaluate_coding_step(gateway)
    except JevGatewayError as error:
        print(json.dumps(error.to_dict()), file=sys.stderr)
        sys.exit(2)
    finally:
        gateway.close()

if __name__ == "__main__":
    main()
