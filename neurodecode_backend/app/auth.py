from __future__ import annotations

import asyncio

from fastapi import Header, HTTPException, WebSocket

from app.firebase_admin_init import ensure_firebase_admin_initialized

try:
    from firebase_admin import auth as firebase_auth
except Exception:
    firebase_auth = None


def _extract_bearer_token(header_value: str | None) -> str | None:
    if not header_value:
        return None
    parts = header_value.strip().split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


def _verify_token_sync(token: str) -> str:
    if firebase_auth is None or not ensure_firebase_admin_initialized():
        raise RuntimeError("firebase_admin not available")
    # check_revoked intentionally left at its default (False): anonymous auth
    # has no logout-everywhere/password-reset flow that revocation protects
    # against, and enabling it adds a Firebase round-trip to every
    # authenticated request on the low-latency live-session path.
    decoded = firebase_auth.verify_id_token(token)
    uid = decoded.get("uid")
    if not uid:
        raise RuntimeError("token missing uid")
    return str(uid)


async def get_current_uid(authorization: str | None = Header(default=None)) -> str:
    """FastAPI dependency: verifies the Firebase ID token and returns the caller's uid."""
    token = _extract_bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")
    try:
        return await asyncio.to_thread(_verify_token_sync, token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def get_ws_uid(websocket: WebSocket) -> str | None:
    """Same verification for the /ws/live handshake. Returns None on any failure
    so the caller can close the socket without ever accepting it."""
    token = _extract_bearer_token(websocket.headers.get("authorization"))
    if not token:
        return None
    try:
        return await asyncio.to_thread(_verify_token_sync, token)
    except Exception:
        return None


def require_owner(resource_user_id: str | None, uid: str) -> None:
    if resource_user_id != uid:
        raise HTTPException(status_code=403, detail="Forbidden")
