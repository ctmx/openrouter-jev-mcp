#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.gateway import JevGateway, JevGatewayError

def main():
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("[-] Error: OPENROUTER_API_KEY environment variable is not set.", file=sys.stderr)
        print("    Export it with: export OPENROUTER_API_KEY='your_openrouter_key'", file=sys.stderr)
        sys.exit(1)

    gateway = JevGateway(openrouter_api_key=api_key)
    state = {
        "error_summary": "A service cannot reach its upstream authentication endpoint.",
        "environment": "staging",
        "recent_event": "A deployment restarted its proxy layer.",
    }
    questions = {
        "root_cause": {
            "type": "choice",
            "instructions": "What is the most likely root cause?",
            "criteria": {
                "network": "Network, proxy, or DNS connectivity problem",
                "credentials": "Authentication credentials rejected by the upstream",
                "application": "Application logic or runtime problem",
            },
        },
        "requires_escalation": {
            "type": "noul",
            "instructions": "Does this issue need on-call engineer intervention?",
        },
    }

    print("Sending state to OpenRouter for a Jev judgement...")
    try:
        result = gateway.evaluate(state, questions)
        print(json.dumps({"model": result.model, "answers": result.answers}, indent=2))
    except JevGatewayError as error:
        print(json.dumps(error.to_dict()), file=sys.stderr)
        sys.exit(2)
    finally:
        gateway.close()

if __name__ == "__main__":
    main()
