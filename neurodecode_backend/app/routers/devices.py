from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth import get_current_uid
from app.state import push_device_store

router = APIRouter()


@router.post("/push-token")
async def register_push_token(
    payload: dict[str, object],
    profile_id: str | None = None,
    uid: str = Depends(get_current_uid),
) -> dict[str, object]:
    token = str(payload.get("token") or "").strip()
    if not token:
        return {"status": "error", "message": "token is required"}

    platform = str(payload.get("platform") or "").strip() or None
    app_version = str(payload.get("app_version") or "").strip() or None

    item = await push_device_store.register(
        user_id=uid,
        token=token,
        profile_id=profile_id,
        platform=platform,
        app_version=app_version,
    )
    token_tail = token[-8:] if len(token) >= 8 else token
    print(
        f"[push] token registered user_id={uid} profile_id={profile_id or ''} "
        f"platform={platform or 'unknown'} token_tail={token_tail}"
    )
    return {"status": "ok", "item": item}


@router.post("/push-token/deactivate")
async def deactivate_push_token(
    payload: dict[str, object],
    uid: str = Depends(get_current_uid),
) -> dict[str, object]:
    token = str(payload.get("token") or "").strip()
    if not token:
        return {"status": "error", "message": "token is required"}

    updated = await push_device_store.deactivate(user_id=uid, token=token)
    if not updated:
        return {"status": "empty", "message": "Push token not found"}
    return {"status": "ok"}
