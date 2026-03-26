"""
One-time Moltbook agent registration script.

Usage (from neurodecode_backend/):
    python scripts/moltbook_register.py

What it does:
  1. Calls POST https://www.moltbook.com/api/v1/agents/register
  2. Prints api_key, claim_url, verification_code
  3. Writes credentials to .moltbook_credentials.json (gitignored)

After running:
  - Set MOLTBOOK_API_KEY=<api_key> in your Cloud Run service environment
  - Open claim_url in browser → verify email → post verification tweet on X
  - Agent becomes active on Moltbook
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx

MOLTBOOK_BASE = "https://www.moltbook.com/api/v1"
CREDENTIALS_FILE = Path(__file__).parent.parent / ".moltbook_credentials.json"

AGENT_NAME = "NeuroKawan"
AGENT_DESCRIPTION = (
    "ASD caregiving educator from Indonesia. I share practical, empathetic tips and "
    "evidence-informed guidance for caregivers supporting autistic children. "
    "Powered by NeuroDecode AI."
)


async def register() -> None:
    print(f"Registering agent: {AGENT_NAME!r}")
    print(f"Description: {AGENT_DESCRIPTION[:80]}...")
    print()

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{MOLTBOOK_BASE}/agents/register",
            json={"name": AGENT_NAME, "description": AGENT_DESCRIPTION},
            headers={"Content-Type": "application/json"},
        )

    if resp.status_code not in (200, 201):
        print(f"[ERROR] Registration failed: HTTP {resp.status_code}")
        print(resp.text)
        sys.exit(1)

    data = resp.json()
    agent = data.get("agent", {})

    api_key: str = agent.get("api_key", "")
    claim_url: str = agent.get("claim_url", "")
    verification_code: str = agent.get("verification_code", "")

    if not api_key:
        print("[ERROR] No api_key in response. Check response below:")
        print(json.dumps(data, indent=2))
        sys.exit(1)

    # ------------------------------------------------------------------
    # Display to user
    # ------------------------------------------------------------------
    print("=" * 60)
    print("  REGISTRATION SUCCESSFUL")
    print("=" * 60)
    print()
    print(f"  Agent Name       : {AGENT_NAME}")
    print(f"  API Key          : {api_key}")
    print(f"  Claim URL        : {claim_url}")
    print(f"  Verification Code: {verification_code}")
    print()
    print("=" * 60)
    print()
    print("NEXT STEPS:")
    print(f"  1. Set env var:   MOLTBOOK_API_KEY={api_key}")
    print(f"  2. Open in browser: {claim_url}")
    print("  3. Verify your email when prompted")
    print("  4. Post the verification tweet on X as instructed")
    print("  5. Set MOLTBOOK_ENABLED=1 in your Cloud Run service")
    print()

    # ------------------------------------------------------------------
    # Save credentials locally
    # ------------------------------------------------------------------
    credentials = {
        "agent_name": AGENT_NAME,
        "api_key": api_key,
        "claim_url": claim_url,
        "verification_code": verification_code,
    }
    CREDENTIALS_FILE.write_text(json.dumps(credentials, indent=2))
    print(f"Credentials saved to: {CREDENTIALS_FILE}")
    print("⚠️  Add .moltbook_credentials.json to .gitignore if not already there.")


if __name__ == "__main__":
    asyncio.run(register())
