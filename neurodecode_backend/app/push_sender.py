from __future__ import annotations

import asyncio
from typing import Any

try:
    import firebase_admin
    from firebase_admin import messaging
except Exception:
    firebase_admin = None
    messaging = None


class PushSender:
    """Feature-flagged FCM sender with safe no-op fallback."""

    def __init__(self, *, enabled: bool) -> None:
        self._enabled = enabled
        self._initialized = False

    def _ensure_initialized(self) -> bool:
        if not self._enabled:
            return False
        if firebase_admin is None or messaging is None:
            print("[push_sender] firebase_admin not installed; push disabled")
            return False
        if self._initialized:
            return True

        try:
            if not firebase_admin._apps:
                firebase_admin.initialize_app()
            self._initialized = True
            return True
        except Exception as e:
            print(f"[push_sender] init failed: {e}")
            return False

    def _send(
        self,
        *,
        tokens: list[str],
        title: str,
        body: str,
        data: dict[str, str],
    ) -> dict[str, object]:
        if not tokens:
            return {
                "enabled": self._enabled,
                "initialized": self._initialized,
                "attempted": 0,
                "success_count": 0,
                "failure_count": 0,
                "error": None,
            }

        initialized = self._ensure_initialized()
        if not initialized:
            return {
                "enabled": self._enabled,
                "initialized": False,
                "attempted": len(tokens),
                "success_count": 0,
                "failure_count": len(tokens),
                "error": "push_sender_not_initialized",
            }

        try:
            message = messaging.MulticastMessage(
                tokens=tokens,
                notification=messaging.Notification(title=title, body=body),
                data=data,
            )
            result = messaging.send_each_for_multicast(message)
            return {
                "enabled": self._enabled,
                "initialized": True,
                "attempted": len(tokens),
                "success_count": int(result.success_count),
                "failure_count": int(result.failure_count),
                "error": None,
            }
        except Exception as e:
            return {
                "enabled": self._enabled,
                "initialized": True,
                "attempted": len(tokens),
                "success_count": 0,
                "failure_count": len(tokens),
                "error": str(e),
            }

    async def send_to_tokens(
        self,
        *,
        tokens: list[str],
        title: str,
        body: str,
        data: dict[str, str],
    ) -> dict[str, object]:
        return await asyncio.to_thread(
            self._send,
            tokens=list(tokens),
            title=title,
            body=body,
            data=dict(data),
        )
