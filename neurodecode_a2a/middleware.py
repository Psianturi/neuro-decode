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


class ApiKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Agent card is always public
        if "/.well-known/" in request.url.path:
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
