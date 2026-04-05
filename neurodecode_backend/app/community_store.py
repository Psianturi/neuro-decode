"""
Community Insights Store — shared Firestore layer.

Written by: neurodecode-moltbook (via heartbeat comment harvest)
Read by:    neurodecode-backend (via memory_context.py → relevance_filter.py)

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


def _get_fs_client(project: str | None) -> Any | None:
    try:
        from google.cloud import firestore  # type: ignore
        return firestore.Client(project=project)
    except Exception as exc:
        logger.warning("[CommunityStore] Firestore unavailable: %s", exc)
        return None


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
