from __future__ import annotations

import asyncio
from collections import deque
from typing import Any

try:
    from google.cloud import firestore
except Exception:
    firestore = None


class SessionStore:
    """Persist session summaries with Firestore-first strategy and memory fallback."""

    def __init__(
        self,
        *,
        firestore_enabled: bool,
        firestore_collection: str,
        firestore_event_collection: str,
        firestore_project: str | None,
        max_memory_items: int = 10,
        max_memory_events: int = 200,
    ) -> None:
        self._firestore_enabled = firestore_enabled
        self._firestore_collection = firestore_collection
        self._firestore_event_collection = firestore_event_collection
        self._firestore_project = firestore_project
        self._client: Any | None = None

        self._memory: deque[dict[str, object]] = deque(maxlen=max_memory_items)
        self._memory_events: deque[dict[str, object]] = deque(maxlen=max_memory_events)
        self._memory_lock = asyncio.Lock()
        self._memory_events_lock = asyncio.Lock()

    def _matches_scope(
        self,
        record: dict[str, object],
        *,
        user_id: str | None,
        profile_id: str | None,
    ) -> bool:
        if user_id and record.get("user_id") != user_id:
            return False
        if profile_id and record.get("profile_id") != profile_id:
            return False
        return True

    def _get_client(self):
        if not self._firestore_enabled:
            return None
        if firestore is None:
            return None
        if self._client is None:
            self._client = firestore.Client(project=self._firestore_project)
        return self._client

    async def _remember_memory(self, record: dict[str, object]) -> None:
        async with self._memory_lock:
            self._memory.appendleft(dict(record))

    async def _remember_events(self, records: list[dict[str, object]]) -> None:
        async with self._memory_events_lock:
            for record in records:
                self._memory_events.appendleft(dict(record))

    def _write_firestore(self, record: dict[str, object]) -> None:
        client = self._get_client()
        if client is None:
            raise RuntimeError("Firestore client unavailable")
        client.collection(self._firestore_collection).add(record)

    def _write_firestore_events(self, records: list[dict[str, object]]) -> None:
        client = self._get_client()
        if client is None:
            raise RuntimeError("Firestore client unavailable")

        batch = client.batch()
        collection = client.collection(self._firestore_event_collection)
        for record in records:
            batch.create(collection.document(), record)
        batch.commit()

    def _fetch_firestore_recent(
        self,
        limit: int,
        *,
        user_id: str | None = None,
        profile_id: str | None = None,
    ) -> list[dict[str, object]]:
        client = self._get_client()
        if client is None:
            raise RuntimeError("Firestore client unavailable")

        query = client.collection(self._firestore_collection)
        if user_id:
            query = query.where("user_id", "==", user_id)
        if profile_id:
            query = query.where("profile_id", "==", profile_id)
        query = query.order_by(
            "timestamp_utc", direction=firestore.Query.DESCENDING
        ).limit(limit)

        out: list[dict[str, object]] = []
        for doc in query.stream():
            item = dict(doc.to_dict() or {})
            item["id"] = doc.id
            out.append(item)
        return out

    async def store(self, record: dict[str, object]) -> None:
        await self._remember_memory(record)

        if not self._firestore_enabled:
            return

        try:
            await asyncio.to_thread(self._write_firestore, dict(record))
        except Exception as e:
            print(f"[session_store] Firestore write failed; using memory fallback: {e}")

    async def store_events(self, records: list[dict[str, object]]) -> None:
        if not records:
            return

        await self._remember_events(records)

        if not self._firestore_enabled:
            return

        try:
            await asyncio.to_thread(self._write_firestore_events, [dict(record) for record in records])
        except Exception as e:
            print(f"[session_store] Firestore event write failed; using memory fallback: {e}")

    async def get_latest(
        self,
        *,
        user_id: str | None = None,
        profile_id: str | None = None,
    ) -> dict[str, object] | None:
        if self._firestore_enabled:
            try:
                items = await asyncio.to_thread(
                    self._fetch_firestore_recent,
                    1,
                    user_id=user_id,
                    profile_id=profile_id,
                )
                if items:
                    return items[0]
            except Exception as e:
                print(f"[session_store] Firestore read latest failed; using memory fallback: {e}")

        async with self._memory_lock:
            items = [
                dict(item)
                for item in self._memory
                if self._matches_scope(item, user_id=user_id, profile_id=profile_id)
            ]
            if not items:
                return None
            return items[0]

    async def list_recent(
        self,
        limit: int,
        *,
        user_id: str | None = None,
        profile_id: str | None = None,
    ) -> list[dict[str, object]]:
        if self._firestore_enabled:
            try:
                return await asyncio.to_thread(
                    self._fetch_firestore_recent,
                    limit,
                    user_id=user_id,
                    profile_id=profile_id,
                )
            except Exception as e:
                print(f"[session_store] Firestore read list failed; using memory fallback: {e}")

        async with self._memory_lock:
            items = [
                dict(item)
                for item in self._memory
                if self._matches_scope(item, user_id=user_id, profile_id=profile_id)
            ]
            return items[:limit]
