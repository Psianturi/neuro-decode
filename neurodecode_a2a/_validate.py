"""A2A v1 migration validation script."""
import urllib.request
import json
import os
import sys

KEY = (
    os.getenv("NEURODECODE_A2A_API_KEY")
    or os.getenv("A2A_API_KEY")
    or ""
)
BASE = (
    os.getenv("NEURODECODE_A2A_BASE_URL")
    or "https://neurodecode-a2a-jzfv6ygw3q-as.a.run.app"
).rstrip("/")
URL = BASE + "/"

if not KEY:
    print(
        "ERROR: Missing A2A API key. Set NEURODECODE_A2A_API_KEY or A2A_API_KEY before running this script."
    )
    sys.exit(2)

results = []


def check(label, ok):
    status = "PASS" if ok else "FAIL"
    results.append((ok, label))
    print(f"  [{status}] {label}")
    return ok


def call_a2a(label, text, use_kind=False):
    part = {"kind": "text", "text": text} if use_kind else {"text": text}
    body = json.dumps({
        "jsonrpc": "2.0", "id": "t1", "method": "SendMessage",
        "params": {"id": "t1", "message": {"role": "user", "parts": [part]}}
    }).encode()
    req = urllib.request.Request(
        URL, data=body,
        headers={"Content-Type": "application/json", "X-API-Key": KEY},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            data = json.loads(r.read().decode())
        text_out = None
        try:
            text_out = data["result"]["artifacts"][0]["parts"][0]["text"]
        except Exception:
            pass
        if not text_out:
            try:
                text_out = data["result"]["status"]["message"]["parts"][0]["text"]
            except Exception:
                pass
        part0 = data.get("result", {}).get("artifacts", [{}])[0].get("parts", [{}])[0] if data.get("result", {}).get("artifacts") else {}
        has_type = part0.get("type") == "text"
        check(f"{label} [parts type=text]", has_type)
        # A2A v1 §4.1.3 + §5.5: state enum must be SCREAMING_SNAKE_CASE ProtoJSON form
        state = data.get("result", {}).get("status", {}).get("state", "")
        check(f"{label} [status.state=TASK_STATE_COMPLETED]", state == "TASK_STATE_COMPLETED")
        ok = bool(text_out and len(text_out) > 10)
        check(label, ok)
        if ok:
            print(f"         -> {text_out[:150]}")
        else:
            print(f"         -> raw: {json.dumps(data)[:250]}")
        return ok
    except Exception as exc:
        check(label, False)
        print(f"         -> ERROR: {exc}")
        return False


# ── 1. Agent Card v1 Check ──────────────────────────────────────────────────
print("\n=== TEST 1: Agent Card v1 Compliance ===")
try:
    req = urllib.request.Request(
        BASE + "/.well-known/agent-card.json",
        headers={"X-API-Key": KEY},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        card = json.loads(r.read().decode())
    check("supportedInterfaces present", "supportedInterfaces" in card)
    check("top-level url absent", "url" not in card)
    check("preferredTransport absent", "preferredTransport" not in card)
    check("stateTransitionHistory absent", "stateTransitionHistory" not in card.get("capabilities", {}))
    api_key_scheme = card.get("securitySchemes", {}).get("apiKey", {})
    check("securitySchemes.apiKey.type=apiKey", api_key_scheme.get("type") == "apiKey")
    check("securitySchemes.apiKey.in=header", api_key_scheme.get("in") == "header")
    check("securitySchemes.apiKey.name=X-API-Key", api_key_scheme.get("name") == "X-API-Key")
    check("security present", isinstance(card.get("security"), list))
    check("version 1.1.0", card.get("version") == "1.1.0")
    check("defaultInputModes text/plain", "text/plain" in card.get("defaultInputModes", []))
except Exception as exc:
    print(f"  [FAIL] Agent card fetch error: {exc}")

# ── 2. v1 Format (no kind) ──────────────────────────────────────────────────
print("\n=== TEST 2: v1 Format (field-presence, no kind) ===")
call_a2a("de-escalation v1-format", "Provide de-escalation steps. Child rocking, vocal distress, audio triggers (loud noise).", use_kind=False)

# ── 3. v0.x Format (with kind) backward compat ─────────────────────────────
print("\n=== TEST 3: v0.x Format (kind discriminator, backward compat) ===")
call_a2a("escalation risk v0.x-format", "Assess escalation risk: child hitting walls, non-verbal for 30 minutes, trigger #3.", use_kind=True)

# ── Summary ──────────────────────────────────────────────────────────────────
print()
passed = sum(1 for ok, _ in results if ok)
total = len(results)
print(f"=== RESULT: {passed}/{total} PASS ===")
for ok, lbl in results:
    print(f"  [{'PASS' if ok else 'FAIL'}] {lbl}")
