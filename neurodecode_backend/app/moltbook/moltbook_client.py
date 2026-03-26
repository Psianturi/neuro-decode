"""
Thin async HTTP client for the Moltbook REST API.
Base URL: https://www.moltbook.com/api/v1

SECURITY: API key is ONLY ever sent to www.moltbook.com.
          Never forward it to any third-party URL.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

MOLTBOOK_BASE = "https://www.moltbook.com/api/v1"
_TIMEOUT = httpx.Timeout(30.0)


class MoltbookClient:
    def __init__(self, api_key: str) -> None:
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{MOLTBOOK_BASE}{path}"
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url, headers=self._headers, params=params or {})
        resp.raise_for_status()
        return resp.json()

    async def _post(self, path: str, body: dict) -> dict:
        url = f"{MOLTBOOK_BASE}{path}"
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(url, headers=self._headers, json=body)
        resp.raise_for_status()
        return resp.json()

    async def _patch(self, path: str, body: dict) -> dict:
        url = f"{MOLTBOOK_BASE}{path}"
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.patch(url, headers=self._headers, json=body)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Account
    # ------------------------------------------------------------------

    async def home(self) -> dict:
        """One-shot dashboard — call first at every heartbeat."""
        return await self._get("/home")

    async def me(self) -> dict:
        return await self._get("/agents/me")

    async def status(self) -> dict:
        return await self._get("/agents/status")

    async def update_profile(self, description: str) -> dict:
        return await self._patch("/agents/me", {"description": description})

    # ------------------------------------------------------------------
    # Feed & posts
    # ------------------------------------------------------------------

    async def get_feed(
        self, sort: str = "hot", limit: int = 25, cursor: str | None = None
    ) -> dict:
        params: dict[str, Any] = {"sort": sort, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        return await self._get("/feed", params)

    async def get_post(self, post_id: str) -> dict:
        return await self._get(f"/posts/{post_id}")

    async def create_post(
        self,
        submolt_name: str,
        title: str,
        content: str = "",
        post_type: str = "text",
    ) -> dict:
        return await self._post(
            "/posts",
            {
                "submolt_name": submolt_name,
                "title": title,
                "content": content,
                "type": post_type,
            },
        )

    async def delete_post(self, post_id: str) -> dict:
        url = f"{MOLTBOOK_BASE}/posts/{post_id}"
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.delete(url, headers=self._headers)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Comments
    # ------------------------------------------------------------------

    async def get_comments(
        self,
        post_id: str,
        sort: str = "best",
        limit: int = 35,
        cursor: str | None = None,
    ) -> dict:
        params: dict[str, Any] = {"sort": sort, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        return await self._get(f"/posts/{post_id}/comments", params)

    async def add_comment(
        self, post_id: str, content: str, parent_id: str | None = None
    ) -> dict:
        body: dict[str, Any] = {"content": content}
        if parent_id:
            body["parent_id"] = parent_id
        return await self._post(f"/posts/{post_id}/comments", body)

    # ------------------------------------------------------------------
    # Voting
    # ------------------------------------------------------------------

    async def upvote_post(self, post_id: str) -> dict:
        return await self._post(f"/posts/{post_id}/upvote", {})

    async def upvote_comment(self, comment_id: str) -> dict:
        return await self._post(f"/comments/{comment_id}/upvote", {})

    # ------------------------------------------------------------------
    # Submolts
    # ------------------------------------------------------------------

    async def list_submolts(self) -> dict:
        return await self._get("/submolts")

    async def subscribe_submolt(self, name: str) -> dict:
        return await self._post(f"/submolts/{name}/subscribe", {})

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------

    async def read_notifications_by_post(self, post_id: str) -> dict:
        return await self._post(f"/notifications/read-by-post/{post_id}", {})

    async def read_all_notifications(self) -> dict:
        return await self._post("/notifications/read-all", {})

    # ------------------------------------------------------------------
    # Verification challenge submit
    # ------------------------------------------------------------------

    async def verify(self, verification_code: str, answer: str) -> dict:
        return await self._post(
            "/verify",
            {"verification_code": verification_code, "answer": answer},
        )

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        search_type: str = "posts",
        limit: int = 10,
        cursor: str | None = None,
    ) -> dict:
        params: dict[str, Any] = {"q": query, "type": search_type, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        return await self._get("/search", params)

    # ------------------------------------------------------------------
    # Follow
    # ------------------------------------------------------------------

    async def follow(self, molty_name: str) -> dict:
        return await self._post(f"/agents/{molty_name}/follow", {})


# ---------------------------------------------------------------------------
# One-time registration (called by setup endpoint, not heartbeat)
# ---------------------------------------------------------------------------

async def register_agent(name: str, description: str) -> dict:
    """
    Register a brand-new agent. Returns api_key, claim_url, verification_code.
    No auth header needed — this is a public endpoint.
    """
    url = f"{MOLTBOOK_BASE}/agents/register"
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            url,
            json={"name": name, "description": description},
            headers={"Content-Type": "application/json"},
        )
    resp.raise_for_status()
    return resp.json()
