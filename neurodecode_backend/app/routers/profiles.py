from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.auth import get_current_uid
from app.memory_context import build_private_memory_context
from app.state import profile_store, session_store

router = APIRouter()


@router.get("/{profile_id}")
async def profile_get(profile_id: str, uid: str = Depends(get_current_uid)) -> dict[str, object]:
    profile = await profile_store.get_profile(profile_id, user_id=uid)
    if profile is None:
        return {
            "status": "empty",
            "message": "Profile not found",
            "profile_id": profile_id,
        }
    return {"status": "ok", "profile": profile}


@router.put("/{profile_id}")
async def profile_upsert(
    profile_id: str,
    payload: dict[str, object],
    uid: str = Depends(get_current_uid),
) -> dict[str, object]:
    record = dict(payload)
    record["profile_id"] = profile_id
    record["user_id"] = uid
    record["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    await profile_store.upsert_profile(profile_id, record, user_id=uid)
    return {"status": "ok", "profile": record}


@router.get("/{profile_id}/memory")
async def profile_memory_list(
    profile_id: str,
    limit: int = 10,
    uid: str = Depends(get_current_uid),
) -> dict[str, object]:
    safe_limit = max(1, min(limit, 50))
    items = await profile_store.list_profile_memory(
        profile_id,
        safe_limit,
        user_id=uid,
    )
    return {
        "status": "ok",
        "profile_id": profile_id,
        "count": len(items),
        "items": items,
    }


@router.post("/{profile_id}/memory")
async def profile_memory_add(
    profile_id: str,
    payload: dict[str, object],
    uid: str = Depends(get_current_uid),
) -> dict[str, object]:
    record = dict(payload)
    record["profile_id"] = profile_id
    record["user_id"] = uid
    record.setdefault("active", True)
    record.setdefault("confidence", "medium")
    record["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    await profile_store.add_profile_memory(profile_id, record, user_id=uid)
    return {"status": "ok", "item": record}


@router.get("/{profile_id}/memory-context")
async def profile_memory_context(
    profile_id: str,
    uid: str = Depends(get_current_uid),
) -> dict[str, object]:
    profile = await profile_store.get_profile(profile_id, user_id=uid)
    items = await profile_store.list_profile_memory(profile_id, 5, user_id=uid)
    sessions = await session_store.list_recent(5, user_id=uid, profile_id=profile_id)
    context = build_private_memory_context(
        profile=profile,
        profile_memory_items=items,
        recent_sessions=sessions,
    )
    return {
        "status": "ok",
        "profile_id": profile_id,
        "profile_found": profile is not None,
        "memory_item_count": len(items),
        "recent_session_count": len(sessions),
        "context": context,
    }
