from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_uid_compat
from app.state import notification_store

router = APIRouter()


@router.get("")
async def notifications_list(
    profile_id: str | None = None,
    status: str | None = None,
    limit: int = 20,
    uid: str = Depends(get_uid_compat),
) -> dict[str, object]:
    safe_limit = max(1, min(limit, 100))
    safe_status = status.strip().lower() if isinstance(status, str) and status.strip() else None
    items = await notification_store.list_recent(
        safe_limit,
        user_id=uid,
        profile_id=profile_id,
        status=safe_status,
    )
    return {
        "status": "ok",
        "count": len(items),
        "items": items,
    }


@router.post("/{notification_id}/read")
async def notifications_mark_read(
    notification_id: str,
    uid: str = Depends(get_uid_compat),
) -> dict[str, object]:
    result = await notification_store.mark_read(notification_id, user_id=uid)
    if result == "forbidden":
        raise HTTPException(status_code=403, detail="Forbidden")
    if result == "not_found":
        return {
            "status": "empty",
            "message": "Notification not found",
            "notification_id": notification_id,
        }
    return {"status": "ok", "notification_id": notification_id}
