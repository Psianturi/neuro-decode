from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

try:
    from google.cloud import firestore
except Exception:
    firestore = None


class NotificationStore:
    """Persist proactive notification items with Firestore-first strategy."""

    def __init__(
        self,
        *,
        firestore_enabled: bool,
        notification_collection: str,
        firestore_project: str | None,
        max_memory_items: int = 300,
    ) -> None:
        self._firestore_enabled = firestore_enabled
        self._notification_collection = notification_collection
        self._firestore_project = firestore_project
        self._client: Any | None = None

        self._memory: deque[dict[str, object]] = deque(maxlen=max_memory_items)
        self._memory_lock = asyncio.Lock()

    def _get_client(self):
        if not self._firestore_enabled:
            return None
        if firestore is None:
            return None
        if self._client is None:
            self._client = firestore.Client(project=self._firestore_project)
        return self._client

    def _matches_scope(
        self,
        record: dict[str, object],
        *,
        user_id: str | None,
        profile_id: str | None,
        status: str | None,
    ) -> bool:
        if user_id and record.get("user_id") != user_id:
            return False
        if profile_id and record.get("profile_id") != profile_id:
            return False
        if status and str(record.get("status") or "").strip().lower() != status.lower():
            return False
        return True

    async def _remember_many(self, records: list[dict[str, object]]) -> None:
        async with self._memory_lock:
            for record in records:
                self._memory.appendleft(dict(record))

    def _add_many_firestore(self, records: list[dict[str, object]]) -> None:
        client = self._get_client()
        if client is None:
            raise RuntimeError("Firestore client unavailable")

        batch = client.batch()
        collection = client.collection(self._notification_collection)
        for record in records:
            notification_id = str(record.get("notification_id") or uuid4().hex)
            record["notification_id"] = notification_id
            batch.set(collection.document(notification_id), record, merge=True)
        batch.commit()

    def _list_recent_firestore(
        self,
        limit: int,
        *,
        user_id: str | None,
        profile_id: str | None,
        status: str | None,
    ) -> list[dict[str, object]]:
        client = self._get_client()
        if client is None:
            raise RuntimeError("Firestore client unavailable")

        query = client.collection(self._notification_collection)
        if user_id:
            query = query.where("user_id", "==", user_id)
        if profile_id:
            query = query.where("profile_id", "==", profile_id)
        if status:
            query = query.where("status", "==", status)

        query = query.order_by("created_at_utc", direction=firestore.Query.DESCENDING).limit(limit)

        out: list[dict[str, object]] = []
        for doc in query.stream():
            item = dict(doc.to_dict() or {})
            item["notification_id"] = doc.id
            out.append(item)
        return out

    def _mark_read_firestore(self, notification_id: str) -> bool:
        client = self._get_client()
        if client is None:
            raise RuntimeError("Firestore client unavailable")

        doc_ref = client.collection(self._notification_collection).document(notification_id)
        snapshot = doc_ref.get()
        if not snapshot.exists:
            return False

        doc_ref.set(
            {
                "status": "read",
                "read_at_utc": datetime.now(timezone.utc).isoformat(),
                "updated_at_utc": datetime.now(timezone.utc).isoformat(),
            },
            merge=True,
        )
        return True

    async def add_many(self, records: list[dict[str, object]]) -> list[dict[str, object]]:
        if not records:
            return []

        normalized: list[dict[str, object]] = []
        now = datetime.now(timezone.utc).isoformat()
        for record in records:
            item = dict(record)
            item.setdefault("notification_id", uuid4().hex)
            item.setdefault("created_at_utc", now)
            item.setdefault("updated_at_utc", now)
            item.setdefault("status", "unread")
            normalized.append(item)

        await self._remember_many(normalized)

        if self._firestore_enabled:
            try:
                await asyncio.to_thread(self._add_many_firestore, [dict(item) for item in normalized])
            except Exception as e:
                print(f"[notification_store] Firestore write failed; using memory fallback: {e}")

        return normalized

    async def list_recent(
        self,
        limit: int,
        *,
        user_id: str | None = None,
        profile_id: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, object]]:
        if self._firestore_enabled:
            try:
                return await asyncio.to_thread(
                    self._list_recent_firestore,
                    limit,
                    user_id=user_id,
                    profile_id=profile_id,
                    status=status,
                )
            except Exception as e:
                print(f"[notification_store] Firestore read failed; using memory fallback: {e}")

        async with self._memory_lock:
            filtered = [
                dict(item)
                for item in self._memory
                if self._matches_scope(
                    item,
                    user_id=user_id,
                    profile_id=profile_id,
                    status=status,
                )
            ]
            return filtered[:limit]

    async def mark_read(self, notification_id: str, *, user_id: str | None = None) -> bool:
        updated = False
        async with self._memory_lock:
            for idx, item in enumerate(self._memory):
                if str(item.get("notification_id")) != notification_id:
                    continue
                if user_id and item.get("user_id") != user_id:
                    continue
                if str(item.get("status") or "") == "read":
                    return True
                updated_item = dict(item)
                updated_item["status"] = "read"
                updated_item["read_at_utc"] = datetime.now(timezone.utc).isoformat()
                updated_item["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
                self._memory[idx] = updated_item
                updated = True
                break

        if self._firestore_enabled:
            try:
                firestore_updated = await asyncio.to_thread(self._mark_read_firestore, notification_id)
                updated = updated or firestore_updated
            except Exception as e:
                print(f"[notification_store] Firestore mark-read failed: {e}")

        return updated
