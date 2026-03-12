from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from typing import Any

try:
    from google.cloud import firestore
except Exception:
    firestore = None


class ProfileStore:
    """Persist stable profiles and curated memory with Firestore-first strategy."""

    def __init__(
        self,
        *,
        firestore_enabled: bool,
        profile_collection: str,
        profile_memory_collection: str,
        firestore_project: str | None,
        max_memory_items_per_profile: int = 50,
    ) -> None:
        self._firestore_enabled = firestore_enabled
        self._profile_collection = profile_collection
        self._profile_memory_collection = profile_memory_collection
        self._firestore_project = firestore_project
        self._client: Any | None = None

        self._profiles: dict[str, dict[str, object]] = {}
        self._profile_memories: dict[str, deque[dict[str, object]]] = defaultdict(
            lambda: deque(maxlen=max_memory_items_per_profile)
        )
        self._profiles_lock = asyncio.Lock()
        self._profile_memories_lock = asyncio.Lock()

    def _scope_key(self, *, user_id: str | None, profile_id: str) -> str:
        if not user_id:
            return profile_id
        return f"{user_id}:{profile_id}"

    def _get_client(self):
        if not self._firestore_enabled:
            return None
        if firestore is None:
            return None
        if self._client is None:
            self._client = firestore.Client(project=self._firestore_project)
        return self._client

    async def _remember_profile(
        self,
        profile_id: str,
        user_id: str | None,
        record: dict[str, object],
    ) -> None:
        async with self._profiles_lock:
            self._profiles[self._scope_key(user_id=user_id, profile_id=profile_id)] = dict(record)

    async def _remember_profile_memory(
        self,
        profile_id: str,
        user_id: str | None,
        record: dict[str, object],
    ) -> None:
        async with self._profile_memories_lock:
            self._profile_memories[self._scope_key(user_id=user_id, profile_id=profile_id)].appendleft(dict(record))

    def _upsert_profile_firestore(
        self,
        profile_id: str,
        user_id: str | None,
        record: dict[str, object],
    ) -> None:
        client = self._get_client()
        if client is None:
            raise RuntimeError("Firestore client unavailable")
        client.collection(self._profile_collection).document(
            self._scope_key(user_id=user_id, profile_id=profile_id)
        ).set(record, merge=True)

    def _fetch_profile_firestore(
        self,
        profile_id: str,
        user_id: str | None,
    ) -> dict[str, object] | None:
        client = self._get_client()
        if client is None:
            raise RuntimeError("Firestore client unavailable")
        doc = client.collection(self._profile_collection).document(
            self._scope_key(user_id=user_id, profile_id=profile_id)
        ).get()
        if not doc.exists:
            return None
        data = dict(doc.to_dict() or {})
        data["profile_id"] = profile_id
        return data

    def _add_profile_memory_firestore(
        self,
        profile_id: str,
        user_id: str | None,
        record: dict[str, object],
    ) -> None:
        client = self._get_client()
        if client is None:
            raise RuntimeError("Firestore client unavailable")
        client.collection(self._profile_memory_collection).add(record)

    def _list_profile_memory_firestore(
        self,
        profile_id: str,
        user_id: str | None,
        limit: int,
    ) -> list[dict[str, object]]:
        client = self._get_client()
        if client is None:
            raise RuntimeError("Firestore client unavailable")

        query = client.collection(self._profile_memory_collection).where(
            "profile_id", "==", profile_id
        )
        if user_id:
            query = query.where("user_id", "==", user_id)
        query = query.order_by(
            "updated_at_utc", direction=firestore.Query.DESCENDING
        ).limit(limit)

        out: list[dict[str, object]] = []
        for doc in query.stream():
            item = dict(doc.to_dict() or {})
            item["id"] = doc.id
            out.append(item)
        return out

    async def upsert_profile(
        self,
        profile_id: str,
        record: dict[str, object],
        *,
        user_id: str | None = None,
    ) -> None:
        await self._remember_profile(profile_id, user_id, record)

        if not self._firestore_enabled:
            return

        try:
            await asyncio.to_thread(
                self._upsert_profile_firestore,
                profile_id,
                user_id,
                dict(record),
            )
        except Exception as e:
            print(f"[profile_store] Firestore profile write failed; using memory fallback: {e}")

    async def get_profile(
        self,
        profile_id: str,
        *,
        user_id: str | None = None,
    ) -> dict[str, object] | None:
        if self._firestore_enabled:
            try:
                profile = await asyncio.to_thread(
                    self._fetch_profile_firestore,
                    profile_id,
                    user_id,
                )
                if profile is not None:
                    return profile
            except Exception as e:
                print(f"[profile_store] Firestore profile read failed; using memory fallback: {e}")

        async with self._profiles_lock:
            profile = self._profiles.get(self._scope_key(user_id=user_id, profile_id=profile_id))
            return dict(profile) if profile is not None else None

    async def add_profile_memory(
        self,
        profile_id: str,
        record: dict[str, object],
        *,
        user_id: str | None = None,
    ) -> None:
        await self._remember_profile_memory(profile_id, user_id, record)

        if not self._firestore_enabled:
            return

        try:
            await asyncio.to_thread(
                self._add_profile_memory_firestore,
                profile_id,
                user_id,
                dict(record),
            )
        except Exception as e:
            print(f"[profile_store] Firestore profile memory write failed; using memory fallback: {e}")

    async def list_profile_memory(
        self,
        profile_id: str,
        limit: int = 10,
        *,
        user_id: str | None = None,
    ) -> list[dict[str, object]]:
        if self._firestore_enabled:
            try:
                return await asyncio.to_thread(
                    self._list_profile_memory_firestore,
                    profile_id,
                    user_id,
                    limit,
                )
            except Exception as e:
                print(f"[profile_store] Firestore profile memory read failed; using memory fallback: {e}")

        async with self._profile_memories_lock:
            items = self._profile_memories.get(
                self._scope_key(user_id=user_id, profile_id=profile_id)
            )
            if items is None:
                return []
            return [dict(item) for item in list(items)[:limit]]