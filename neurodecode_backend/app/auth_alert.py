from __future__ import annotations

import time
from collections import deque
from urllib import parse as urlparse
from urllib import request as urlrequest

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_WINDOW_SECONDS = 300  # 5 minutes
_THRESHOLD = 20  # alert once this many 401/403s land within the window
_COOLDOWN_SECONDS = 900  # don't re-alert more than once per 15 minutes

_recent_denials: deque[float] = deque()
_last_alert_at = 0.0


def _send_telegram(bot_token: str, chat_id: str, text: str) -> None:
    try:
        api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text}
        encoded = urlparse.urlencode(payload).encode("utf-8")
        req = urlrequest.Request(api_url, data=encoded, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urlrequest.urlopen(req, timeout=10) as resp:
            if resp.status >= 300:
                print(f"[auth_alert] telegram send failed with status {resp.status}")
    except Exception as e:
        print(f"[auth_alert] telegram send failed: {e}")


class AuthDenialAlertMiddleware(BaseHTTPMiddleware):
    """Fires a single Telegram alert if 401/403 responses spike within a
    short window — the fastest signal available that a backend/mobile auth
    mismatch (the failure mode behind the 2026-08-23 incident, where an
    auth-requiring backend deploy went out ahead of the matching app update)
    is happening in production, without waiting for a caregiver to report it.
    """

    def __init__(self, app, *, bot_token: str | None, chat_id: str | None) -> None:
        super().__init__(app)
        self._bot_token = bot_token
        self._chat_id = chat_id

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        if response.status_code in (401, 403) and self._bot_token and self._chat_id:
            now = time.monotonic()
            _recent_denials.append(now)
            while _recent_denials and now - _recent_denials[0] > _WINDOW_SECONDS:
                _recent_denials.popleft()

            global _last_alert_at
            if (
                len(_recent_denials) >= _THRESHOLD
                and now - _last_alert_at > _COOLDOWN_SECONDS
            ):
                _last_alert_at = now
                text = (
                    "NeuroDecode backend alert\n"
                    f"{len(_recent_denials)} auth-denied (401/403) responses "
                    f"in the last {_WINDOW_SECONDS // 60} min.\n"
                    "Likely cause: a deployed backend change now requires auth "
                    "that the currently-installed app isn't sending yet — or a "
                    "genuine probing attempt. Check Cloud Run logs."
                )
                _send_telegram(self._bot_token, self._chat_id, text)

        return response
