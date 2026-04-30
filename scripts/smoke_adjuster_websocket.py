#!/usr/bin/env python3
"""Smoke test: connect to live adjuster WebSocket and test text fallback.

Usage:
    python scripts/smoke_adjuster_websocket.py \\
        --api-url https://claimpilot-devca-api.xxx.azurecontainerapps.io \\
        --claim-id d0755fde7ac7
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import urllib.request


async def smoke_test(api_url: str, claim_id: str) -> int:
    """Connect to WebSocket, send a text query, print responses."""
    # Strip trailing slash
    api_url = api_url.rstrip("/")

    # 1. Verify REST health
    print(f"Checking REST endpoint: {api_url}/docs ...")
    try:
        req = urllib.request.Request(f"{api_url}/docs", method="HEAD")
        urllib.request.urlopen(req, timeout=10)
        print("  REST endpoint OK")
    except Exception as exc:
        print(f"  REST endpoint FAILED: {exc}")
        return 1

    # 2. Verify claim exists via REST
    print(f"Checking claim {claim_id} via REST ...")
    try:
        req = urllib.request.Request(f"{api_url}/api/v1/adjuster/claim/{claim_id}")
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        if not data.get("found"):
            print(f"  Claim {claim_id} not found")
            return 1
        print(f"  Claim found: {data.get('summary', '')[:80]}")
    except Exception as exc:
        print(f"  Claim lookup FAILED: {exc}")
        return 1

    # 3. Connect WebSocket
    ws_url = api_url.replace("https://", "wss://").replace("http://", "ws://")
    ws_url = f"{ws_url}/api/v1/adjuster/voice/{claim_id}"
    print(f"Connecting WebSocket: {ws_url} ...")

    try:
        import websockets
    except ImportError:
        print("  websockets not installed. Run: pip install websockets")
        return 1

    try:
        async with websockets.connect(ws_url, open_timeout=15) as ws:
            print("  WebSocket connected!")

            # Read initial messages (session.config or status)
            initial = await asyncio.wait_for(ws.recv(), timeout=10)
            msg = json.loads(initial)
            msg_type = msg.get("type", "unknown")
            print(f"  Received: type={msg_type}")

            if msg_type == "status":
                print(f"  Mode: {msg.get('mode', 'unknown')}")
                print(f"  Message: {msg.get('message', '')}")

            if msg_type == "session.config":
                print(f"  Session ID: {msg.get('session_id', '')}")

            # 4. Send text fallback query
            query = "what's the fraud score on this claim?"
            print(f"\nSending: {query}")
            await ws.send(json.dumps({"type": "text.input", "text": query}))

            # 5. Read response(s)
            print("Waiting for response ...")
            for _ in range(5):
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=10)
                except TimeoutError:
                    print("  Timeout waiting for response")
                    break

                try:
                    resp_data = json.loads(response)
                except json.JSONDecodeError:
                    print(f"  Non-JSON response: {response[:100]}")
                    continue

                resp_type = resp_data.get("type", "")
                if resp_type == "transcript":
                    role = resp_data.get("role", "?")
                    text = resp_data.get("text", "")
                    print(f"  [{role}] {text}")
                    break
                elif resp_type == "error":
                    print(f"  ERROR: {resp_data.get('message', '')}")
                    return 1
                else:
                    print(f"  Received: {resp_type} — {json.dumps(resp_data)[:120]}")

            print("\nSmoke test PASSED")
            return 0

    except Exception as exc:
        print(f"  WebSocket FAILED: {type(exc).__name__}: {exc}")
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test adjuster WebSocket")
    parser.add_argument("--api-url", required=True, help="API base URL (https://...)")
    parser.add_argument("--claim-id", required=True, help="Claim ID to test with")
    args = parser.parse_args()

    sys.exit(asyncio.run(smoke_test(args.api_url, args.claim_id)))


if __name__ == "__main__":
    main()
