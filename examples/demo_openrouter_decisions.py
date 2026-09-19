#!/usr/bin/env python3
"""
demo_openrouter_decisions.py

Demonstrates calling Jev via OpenRouter's Alpha Decisions API:
Endpoint: POST https://openrouter.ai/api/alpha/decisions
Model: typesafe/jev-1.13
"""

import os
import sys
import json
import httpx

def main():
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("[-] Error: OPENROUTER_API_KEY environment variable is not set.", file=sys.stderr)
        print("    Export it with: export OPENROUTER_API_KEY='your_openrouter_key'", file=sys.stderr)
        sys.exit(1)

    url = "https://openrouter.ai/api/alpha/decisions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "~typesafe/jev-latest",
        "state": {
            "error_log": "ConnectionError: HTTPSConnectionPool(host='api.internal', port=443): Max retries exceeded with url /v1/auth (Caused by NewConnectionError('<urllib3.connection.HTTPSConnection object>: Failed to establish a new connection: [Errno 111] Connection refused'))",
            "environment": "staging-cluster-04",
            "recent_events": "Deployment 2 minutes ago restarted ingress and envoy proxies."
        },
        "questions": {
            "root_cause": {
                "type": "choice",
                "instructions": "What is the most likely root cause of this failure?",
                "criteria": {
                    "network_down": "Service unreachable or proxy configuration / DNS issue",
                    "bad_credentials": "Authentication token expired or rejected by upstream",
                    "code_syntax_error": "Syntax or application logic runtime bug",
                    "resource_exhaustion": "Out of memory or disk space"
                }
            },
            "requires_escalation": {
                "type": "noul",
                "instructions": "Does this issue require on-call engineer intervention?"
            }
        }
    }

    print("[*] Sending request to OpenRouter Decisions endpoint...")
    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=15.0)
        response.raise_for_status()
        data = response.json()
        print("\n[+] Response received successfully:")
        print(json.dumps(data, indent=2))
    except httpx.HTTPStatusError as e:
        print(f"[-] HTTP Error {e.response.status_code}: {e.response.text}", file=sys.stderr)
    except Exception as e:
        print(f"[-] Request failed: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
