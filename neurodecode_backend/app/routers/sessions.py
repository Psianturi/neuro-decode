from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_uid
from app.state import LATEST_SESSION_MAX_ITEMS, session_store

router = APIRouter()


@router.get("/latest")
async def sessions_latest(
    profile_id: str | None = None,
    uid: str = Depends(get_current_uid),
) -> dict[str, object]:
    latest = await session_store.get_latest(user_id=uid, profile_id=profile_id)
    if latest is None:
        return {"status": "empty", "message": "No completed session summary yet"}
    return {"status": "ok", "session": latest}


@router.get("")
async def sessions_list(
    profile_id: str | None = None,
    uid: str = Depends(get_current_uid),
) -> dict[str, object]:
    items = await session_store.list_recent(
        LATEST_SESSION_MAX_ITEMS,
        user_id=uid,
        profile_id=profile_id,
    )
    return {
        "status": "ok",
        "count": len(items),
        "sessions": items,
    }


@router.patch("/{session_id}/rate")
async def sessions_rate(
    session_id: str,
    rating: int,
    uid: str = Depends(get_current_uid),
) -> dict[str, object]:
    if rating < 1 or rating > 5:
        return {"status": "error", "message": "rating must be 1–5"}
    result = await session_store.rate_session(session_id, rating, user_id=uid)
    if result == "forbidden":
        raise HTTPException(status_code=403, detail="Forbidden")
    if result == "not_found":
        return {"status": "empty", "message": "Session not found", "session_id": session_id}
    return {"status": "ok", "session_id": session_id, "caregiver_rating": rating}
