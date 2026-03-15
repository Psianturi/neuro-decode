from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

try:
    from google.cloud import firestore
except Exception:
    firestore = None


class PushDeviceStore:
    """Store push device tokens with Firestore-first strategy."""

    def __init__(
        self,
        *,
        firestore_enabled: bool,
        device_collection: str,
        firestore_project: str | None,
    ) -> None:
        self._firestore_enabled = firestore_enabled
        self._device_collection = device_collection
        self._firestore_project = firestore_project
        self._client: Any | None = None
        self._memory: dict[str, dict[str, object]] = {}
        self._lock = asyncio.Lock()

    def _get_client(self):
        if not self._firestore_enabled:
            return None
        if firestore is None:
            return None
        if self._client is None:
            self._client = firestore.Client(project=self._firestore_project)
        return self._client

    def _device_key(self, *, user_id: str, token: str) -> str:
        return f"{user_id}:{token}"

    async def _remember(self, *, user_id: str, token: str, record: dict[str, object]) -> None:
        async with self._lock:
            self._memory[self._device_key(user_id=user_id, token=token)] = dict(record)

    def _upsert_firestore(self, *, user_id: str, token: str, record: dict[str, object]) -> None:
        client = self._get_client()
        if client is None:
            raise RuntimeError("Firestore client unavailable")
        doc_id = self._device_key(user_id=user_id, token=token)
        client.collection(self._device_collection).document(doc_id).set(record, merge=True)

    def _list_firestore(self, *, user_id: str, profile_id: str | None) -> list[dict[str, object]]:
        client = self._get_client()
        if client is None:
            raise RuntimeError("Firestore client unavailable")

        query = client.collection(self._device_collection).where("user_id", "==", user_id)
        if profile_id:
            query = query.where("profile_id", "==", profile_id)
        query = query.where("active", "==", True)  # noqa: E712

        out: list[dict[str, object]] = []
        for doc in query.stream():
            item = dict(doc.to_dict() or {})
            item["id"] = doc.id
            out.append(item)
        return out

    async def register(
        self,
        *,
        user_id: str,
        token: str,
        profile_id: str | None,
        platform: str | None,
        app_version: str | None,
    ) -> dict[str, object]:
        now = datetime.now(timezone.utc).isoformat()
        record: dict[str, object] = {
            "user_id": user_id,
            "token": token,
            "profile_id": profile_id,
            "platform": (platform or "unknown").strip().lower(),
            "app_version": (app_version or "").strip(),
            "active": True,
            "updated_at_utc": now,
            "registered_at_utc": now,
        }

        await self._remember(user_id=user_id, token=token, record=record)

        if self._firestore_enabled:
            try:
                await asyncio.to_thread(
                    self._upsert_firestore,
                    user_id=user_id,
                    token=token,
                    record=dict(record),
                )
            except Exception as e:
                print(f"[push_device_store] Firestore write failed; using memory fallback: {e}")

        return record

    async def list_active_tokens(self, *, user_id: str, profile_id: str | None = None) -> list[str]:
        items: list[dict[str, object]] = []

        if self._firestore_enabled:
            try:
                items = await asyncio.to_thread(
                    self._list_firestore,
                    user_id=user_id,
                    profile_id=profile_id,
                )
            except Exception as e:
                print(f"[push_device_store] Firestore read failed; using memory fallback: {e}")

        if not items:
            async with self._lock:
                values = list(self._memory.values())
            for row in values:
                if str(row.get("user_id") or "") != user_id:
                    continue
                if profile_id and str(row.get("profile_id") or "") != profile_id:
                    continue
                if row.get("active") is not True:
                    continue
                items.append(dict(row))

        tokens: list[str] = []
        seen: set[str] = set()
        for item in items:
            token = str(item.get("token") or "").strip()
            if not token or token in seen:
                continue
            seen.add(token)
            tokens.append(token)
        return tokens
