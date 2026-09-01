from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import Header, HTTPException, Request, WebSocket

from app.firebase_admin_init import ensure_firebase_admin_initialized
from app.state import settings

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


def _compat_window_open() -> bool:
    """Whether the rollout compatibility window (NEURODECODE_AUTH_COMPAT_DEADLINE_UTC)
    is currently configured and not yet expired. Unset by default, which means
    the fallback below is a no-op unless explicitly opted into at deploy time."""
    deadline_raw = settings.auth_compat_deadline_utc
    if not deadline_raw:
        return False
    try:
        deadline = datetime.fromisoformat(deadline_raw.replace("Z", "+00:00"))
    except ValueError:
        return False
    return datetime.now(timezone.utc) <= deadline


def _compat_fallback_uid(*, legacy_user_id: str | None, path: str) -> str | None:
    """Trust a caller-supplied user_id, unverified — same as the pre-auth
    behavior — only while the compat window is open and only when one is
    actually supplied. This exists solely to let old, not-yet-updated app
    installs keep working while backend auth enforcement ships ahead of full
    mobile adoption; it does not apply to /account/claim-legacy (see
    get_current_uid), since that endpoint's entire job is bridging an
    unverified legacy id to a *verified* one and must not accept an
    unverified id on both sides."""
    if not legacy_user_id or not _compat_window_open():
        return None
    print(f"[auth] compat fallback used (pre-auth client) user_id={legacy_user_id} path={path}")
    return legacy_user_id


async def get_uid_compat(
    request: Request,
    authorization: str | None = Header(default=None),
) -> str:
    """Like get_current_uid, but falls back to the legacy `user_id` query
    param while the rollout compatibility window is open. Prefer a verified
    token whenever one is sent — the fallback only fires when no
    Authorization header is present at all, so an updated app always gets
    the secure path even during the window."""
    token = _extract_bearer_token(authorization)
    if token:
        try:
            return await asyncio.to_thread(_verify_token_sync, token)
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

    legacy_user_id = (request.query_params.get("user_id") or "").strip() or None
    compat_uid = _compat_fallback_uid(legacy_user_id=legacy_user_id, path=request.url.path)
    if compat_uid is not None:
        return compat_uid

    raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")


async def get_ws_uid_compat(websocket: WebSocket) -> str | None:
    """WS counterpart of get_uid_compat. Still returns None (never raises) so
    the caller can reject the handshake cleanly without ever accepting it."""
    token = _extract_bearer_token(websocket.headers.get("authorization"))
    if token:
        try:
            return await asyncio.to_thread(_verify_token_sync, token)
        except Exception:
            return None

    legacy_user_id = (websocket.query_params.get("user_id") or "").strip() or None
    return _compat_fallback_uid(legacy_user_id=legacy_user_id, path="/ws/live")
