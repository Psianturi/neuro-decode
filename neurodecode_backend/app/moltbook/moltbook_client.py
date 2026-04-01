"""
Thin async HTTP client for the Moltbook REST API.
Base URL: https://www.moltbook.com/api/v1

SECURITY: API key is ONLY ever sent to www.moltbook.com.
          Never forward it to any third-party URL.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

MOLTBOOK_BASE = "https://www.moltbook.com/api/v1"
_TIMEOUT = httpx.Timeout(30.0)

# High-confidence spam signals for DM auto-reject
_DM_SPAM_SIGNALS = [
    "approve this dm",
    "send this to your maker",
    "earning on",
    "ranked on",
    "play.google.com/store",
    "apps.apple.com",
    "ball maze",
    "color ball",
]


def _is_dm_spam(preview: str) -> bool:
    """High-confidence spam detection from DM preview. Conservative — only obvious cases."""
    lowered = preview.lower()
    return any(signal in lowered for signal in _DM_SPAM_SIGNALS)


class MoltbookClient:
    def __init__(self, api_key: str) -> None:
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        # Rate limit state — updated from response headers
        self._rate_limit_remaining: int = 60
        self._rate_limit_reset: float = 0.0  # unix timestamp

    def _update_rate_limit(self, resp: httpx.Response) -> None:
        """Parse X-RateLimit headers and update internal state."""
        try:
            remaining = resp.headers.get("X-RateLimit-Remaining")
            reset = resp.headers.get("X-RateLimit-Reset")
            if remaining is not None:
                self._rate_limit_remaining = int(remaining)
            if reset is not None:
                self._rate_limit_reset = float(reset)
            if self._rate_limit_remaining <= 5:
                reset_in = max(0, self._rate_limit_reset - time.time())
                logger.warning(
                    "[MoltbookClient] Rate limit low: remaining=%d reset_in=%.0fs",
                    self._rate_limit_remaining, reset_in,
                )
        except Exception:
            pass

    def is_rate_limited(self) -> bool:
        """True if we should pause requests due to low remaining budget."""
        if self._rate_limit_remaining <= 2:
            if time.time() < self._rate_limit_reset:
                return True
        return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{MOLTBOOK_BASE}{path}"
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url, headers=self._headers, params=params or {})
        self._update_rate_limit(resp)
        resp.raise_for_status()
        return resp.json()

    async def _post(self, path: str, body: dict) -> dict:
        url = f"{MOLTBOOK_BASE}{path}"
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(url, headers=self._headers, json=body)
        self._update_rate_limit(resp)
        resp.raise_for_status()
        return resp.json()

    async def _patch(self, path: str, body: dict) -> dict:
        url = f"{MOLTBOOK_BASE}{path}"
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.patch(url, headers=self._headers, json=body)
        self._update_rate_limit(resp)
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
        self._update_rate_limit(resp)
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
    # Agent profile (used to check existing posts before onboarding)
    # ------------------------------------------------------------------

    async def get_agent_profile(self, name: str) -> dict:
        return await self._get("/agents/profile", {"name": name})

    # ------------------------------------------------------------------
    # Follow
    # ------------------------------------------------------------------

    async def follow(self, molty_name: str) -> dict:
        return await self._post(f"/agents/{molty_name}/follow", {})

    # ------------------------------------------------------------------
    # Direct Messages (MESSAGING.md)
    # ------------------------------------------------------------------

    async def dm_check(self) -> dict:
        """Quick DM activity check — pending requests + unread count."""
        return await self._get("/agents/dm/check")

    async def dm_requests(self) -> dict:
        """List pending DM requests (other agents want to chat)."""
        return await self._get("/agents/dm/requests")

    async def dm_approve_request(self, conversation_id: str) -> dict:
        return await self._post(f"/agents/dm/requests/{conversation_id}/approve", {})

    async def dm_reject_request(self, conversation_id: str, block: bool = False) -> dict:
        """Reject a DM request. Set block=True to also block the sender."""
        return await self._post(
            f"/agents/dm/requests/{conversation_id}/reject",
            {"block": block} if block else {},
        )

    async def dm_conversations(self) -> dict:
        """List approved/active DM conversations."""
        return await self._get("/agents/dm/conversations")

    async def dm_read_conversation(self, conversation_id: str) -> dict:
        """Read a conversation — also marks its messages as read."""
        return await self._get(f"/agents/dm/conversations/{conversation_id}")

    async def dm_send_message(self, conversation_id: str, message: str) -> dict:
        return await self._post(
            f"/agents/dm/conversations/{conversation_id}/send",
            {"message": message},
        )


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
