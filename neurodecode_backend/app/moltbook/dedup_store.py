"""
Firestore-backed dedup state store for Moltbook heartbeat.

Persists 4 dedup sets across cold starts so the agent doesn't
reply/comment/upvote the same content twice after a container restart.

Design decisions:
- Single Firestore document: moltbook_agent_state/dedup_ids
- Only stores IDs with timestamps — TTL eviction drops entries >7 days old
- Loaded once at first heartbeat, flushed after each cycle
- Falls back silently to in-memory if Firestore unavailable
- Never stores post_count / cycle_count — those are cosmetic counters
- Also persists agent flags (subscribed, intro_posted) to survive cold start
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

_COLLECTION = "moltbook_agent_state"
_DOC_ID = "dedup_ids"
_FLAGS_DOC_ID = "agent_flags"  # separate doc for boolean flags
_TTL_DAYS = 7

# Keys in _state that we persist (set name → Firestore field name)
_PERSIST_SETS = {
    "replied_comment_ids": "replied_comment_ids",
    "commented_post_ids": "commented_post_ids",
    "upvoted_comment_ids": "upvoted_comment_ids",
    "upvoted_post_ids": "upvoted_post_ids",
}


def _cutoff_iso() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=_TTL_DAYS)).isoformat()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_fs_client(project: str | None) -> Any | None:
    try:
        from google.cloud import firestore  # type: ignore
        return firestore.Client(project=project)
    except Exception as exc:
        logger.warning("[DedupeStore] Firestore client unavailable: %s", exc)
        return None


def _load_sync(project: str | None) -> dict[str, set]:
    """
    Load dedup sets from Firestore. Returns dict of set_name -> set of IDs.
    Evicts entries older than TTL_DAYS.
    """
    client = _get_fs_client(project)
    if client is None:
        return {}

    try:
        doc = client.collection(_COLLECTION).document(_DOC_ID).get()
        if not doc.exists:
            return {}

        data = doc.to_dict() or {}
        cutoff = _cutoff_iso()
        result: dict[str, set] = {}

        for set_name in _PERSIST_SETS.values():
            raw: dict = data.get(set_name, {})
            # raw is {id: iso_timestamp} — filter out expired
            live = {k for k, ts in raw.items() if isinstance(ts, str) and ts >= cutoff}
            if live:
                result[set_name] = live

        total = sum(len(s) for s in result.values())
        logger.warning("[DedupeStore] Loaded %d IDs across %d sets from Firestore", total, len(result))
        return result

    except Exception as exc:
        logger.warning("[DedupeStore] Load failed: %s", exc)
        return {}


def _flush_sync(project: str | None, state: dict[str, Any]) -> None:
    """
    Write current dedup sets to Firestore.
    Stores {id: timestamp} so TTL eviction works on next load.
    """
    client = _get_fs_client(project)
    if client is None:
        return

    now = _now_iso()
    cutoff = _cutoff_iso()
    payload: dict[str, Any] = {"updated_at": now}

    for state_key, field_name in _PERSIST_SETS.items():
        ids: set = state.get(state_key, set())
        # Cap at 2000 most-recent IDs per set to bound document size
        # (Firestore doc limit is 1MB; each entry ~60 bytes → 2000 = ~120KB)
        if len(ids) > 2000:
            ids = set(list(ids)[-2000:])
        payload[field_name] = {id_: now for id_ in ids}

    try:
        client.collection(_COLLECTION).document(_DOC_ID).set(payload)
        total = sum(len(v) for v in payload.values() if isinstance(v, dict))
        logger.warning("[DedupeStore] Flushed %d IDs to Firestore", total)
    except Exception as exc:
        logger.warning("[DedupeStore] Flush failed: %s", exc)


async def load_dedup_state(project: str | None, state: dict[str, Any]) -> None:
    """
    Load persisted dedup IDs and agent flags into _state.
    Called once at first heartbeat cycle.
    """
    loaded = await asyncio.to_thread(_load_sync, project)
    for state_key, field_name in _PERSIST_SETS.items():
        if field_name in loaded:
            state[state_key].update(loaded[field_name])

    # Load agent flags (subscribed, intro_posted)
    flags = await asyncio.to_thread(_load_flags_sync, project)
    if flags.get("subscribed"):
        state["subscribed"] = True
    if flags.get("intro_posted"):
        state["intro_posted"] = True
    if flags.get("subscribed") or flags.get("intro_posted"):
        logger.warning("[DedupeStore] Loaded agent flags: subscribed=%s intro_posted=%s",
                       flags.get("subscribed"), flags.get("intro_posted"))


async def flush_dedup_state(project: str | None, state: dict[str, Any]) -> None:
    """
    Persist current dedup sets and agent flags to Firestore.
    Called at end of each heartbeat cycle.
    """
    await asyncio.to_thread(_flush_sync, project, state)
    await asyncio.to_thread(_flush_flags_sync, project, state)


def _load_flags_sync(project: str | None) -> dict[str, bool]:
    client = _get_fs_client(project)
    if client is None:
        return {}
    try:
        doc = client.collection(_COLLECTION).document(_FLAGS_DOC_ID).get()
        if not doc.exists:
            return {}
        return doc.to_dict() or {}
    except Exception as exc:
        logger.warning("[DedupeStore] Load flags failed: %s", exc)
        return {}


def _flush_flags_sync(project: str | None, state: dict[str, Any]) -> None:
    client = _get_fs_client(project)
    if client is None:
        return
    try:
        payload = {
            "subscribed": bool(state.get("subscribed")),
            "intro_posted": bool(state.get("intro_posted")),
            "updated_at": _now_iso(),
        }
        client.collection(_COLLECTION).document(_FLAGS_DOC_ID).set(payload)
    except Exception as exc:
        logger.warning("[DedupeStore] Flush flags failed: %s", exc)
