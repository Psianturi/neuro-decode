from __future__ import annotations

import asyncio
from collections import deque
from typing import Any


class RuleDebugStore:
    """In-memory debug trail for proactive rule evaluations.

    This store is intentionally ephemeral and read-only from API endpoints.
    It helps inspect why proactive rules were (or were not) triggered without
    touching live session behavior.
    """

    def __init__(self, *, max_items: int = 300) -> None:
        self._items: deque[dict[str, object]] = deque(maxlen=max_items)
        self._lock = asyncio.Lock()

    async def add(self, record: dict[str, object]) -> None:
        async with self._lock:
            self._items.appendleft(dict(record))

    async def list_recent(
        self,
        *,
        limit: int,
        user_id: str | None = None,
        profile_id: str | None = None,
        rule_id: str | None = None,
        session_id: str | None = None,
    ) -> list[dict[str, object]]:
        safe_limit = max(1, min(limit, 200))

        def _matches(item: dict[str, Any]) -> bool:
            if user_id and str(item.get("user_id") or "") != user_id:
                return False
            if profile_id and str(item.get("profile_id") or "") != profile_id:
                return False
            if session_id and str(item.get("session_id") or "") != session_id:
                return False
            if rule_id:
                evaluations = item.get("evaluations")
                if not isinstance(evaluations, list):
                    return False
                found = False
                for entry in evaluations:
                    if not isinstance(entry, dict):
                        continue
                    if str(entry.get("rule_id") or "") == rule_id:
                        found = True
                        break
                if not found:
                    return False
            return True

        async with self._lock:
            out: list[dict[str, object]] = []
            for item in self._items:
                row = dict(item)
                if not _matches(row):
                    continue
                out.append(row)
                if len(out) >= safe_limit:
                    break
            return out
