"""API key middleware — loaded once at startup from Secret Manager or env."""
from __future__ import annotations

import os
import logging

from fastapi import Header, HTTPException

logger = logging.getLogger(__name__)

_valid_keys: set[str] = set()


def load_api_keys() -> None:
    """Call once at startup. Loads key from env (set via Secret Manager mount)."""
    key = (os.getenv("A2A_API_KEY") or "").strip()
    if key:
        _valid_keys.add(key)
        logger.info("[middleware] A2A API key loaded")
    else:
        logger.warning("[middleware] A2A_API_KEY not set — all requests will be rejected")


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if not _valid_keys:
        raise HTTPException(status_code=503, detail="API key not configured")
    if not x_api_key or x_api_key.strip() not in _valid_keys:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")
