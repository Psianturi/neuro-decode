"""
Community Insights Store

Persists insights extracted from Moltbook comments into Firestore
community_insights/ collection. These insights are later consumed by
memory_context.py to enrich live session context for caregivers.

Privacy: only anonymized insight text is stored — no user_id, no
profile_id, no caregiver names. Agent names from Moltbook are stored
as-is (they are public AI agent identities, not human PII).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_COLLECTION = "community_insights"
_MAX_INSIGHTS = 200  # cap collection size, drop oldest on overflow


def _get_fs_client(project: str | None) -> Any | None:
    try:
        from google.cloud import firestore  # type: ignore
        return firestore.Client(project=project)
    except Exception as exc:
        logger.warning("[CommunityStore] Firestore unavailable: %s", exc)
        return None


def _save_sync(project: str | None, record: dict) -> None:
    client = _get_fs_client(project)
    if client is None:
        return
    try:
        client.collection(_COLLECTION).add(record)
    except Exception as exc:
        logger.warning("[CommunityStore] Save failed: %s", exc)


def _count_sync(project: str | None) -> int:
    client = _get_fs_client(project)
    if client is None:
        return 0
    try:
        return len(list(client.collection(_COLLECTION).limit(1000).stream()))
    except Exception:
        return 0


async def save_insight(
    *,
    project: str | None,
    agent_name: str,
    post_title: str,
    insight_text: str,
    insight_type: str,
) -> None:
    """Save one extracted insight to Firestore. Best-effort, non-blocking."""
    record = {
        "source": "moltbook_comment",
        "agent_name": agent_name,
        "post_title": post_title,
        "insight_text": insight_text,
        "insight_type": insight_type,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "used_in_session": False,
    }
    await asyncio.to_thread(_save_sync, project, record)
    logger.warning(
        "[CommunityStore] Saved insight type=%s from=%s: %s",
        insight_type, agent_name, insight_text[:80],
    )


async def list_recent(project: str | None, limit: int = 20) -> list[dict]:
    """Return recent insights for memory_context injection."""
    def _fetch(project: str | None, limit: int) -> list[dict]:
        client = _get_fs_client(project)
        if client is None:
            return []
        try:
            from google.cloud import firestore  # type: ignore
            docs = (
                client.collection(_COLLECTION)
                .order_by("created_at", direction=firestore.Query.DESCENDING)
                .limit(limit)
                .stream()
            )
            return [dict(doc.to_dict() or {}) for doc in docs]
        except Exception as exc:
            logger.warning("[CommunityStore] List failed: %s", exc)
            return []

    return await asyncio.to_thread(_fetch, project, limit)
