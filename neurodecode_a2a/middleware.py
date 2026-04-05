"""API key middleware — validates X-API-Key on all requests except agent card."""
from __future__ import annotations

import logging
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

_VALID_KEYS: set[str] = set()


def load_api_keys() -> None:
    """Load API key from environment variable (injected by Cloud Run --update-secrets)."""
    key = (os.getenv("A2A_API_KEY") or "").strip()
    if key:
        _VALID_KEYS.add(key)
        logger.info("[startup] A2A API key loaded (%d chars)", len(key))
    else:
        logger.warning("[startup] A2A_API_KEY not set — all requests will be rejected")


def require_api_key(request: Request) -> bool:
    """Return True if the request must be authenticated.

    Auth is skipped when A2A_REQUIRE_AUTH=0 (since Prompt Opinion platform does not forward API keys by default).
    Set A2A_REQUIRE_AUTH=1 to enforce in private/production use.
    """
    return os.getenv("A2A_REQUIRE_AUTH", "0").strip() == "1"


class ApiKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Agent card and health check are always public
        if "/.well-known/" in request.url.path or request.url.path == "/health":
            return await call_next(request)

        # Auth enforcement controlled by env var
        if not require_api_key(request):
            return await call_next(request)

        api_key = request.headers.get("X-API-Key", "")
        if not api_key:
            logger.warning("security_rejected_missing_api_key path=%s", request.url.path)
            return JSONResponse(
                status_code=401,
                content={"error": "Unauthorized", "detail": "X-API-Key header is required"},
            )
        if api_key not in _VALID_KEYS:
            logger.warning("security_rejected_invalid_api_key key_prefix=%s", api_key[:6])
            return JSONResponse(
                status_code=403,
                content={"error": "Forbidden", "detail": "Invalid API key"},
            )
        return await call_next(request)
