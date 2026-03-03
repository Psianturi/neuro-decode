from __future__ import annotations

import base64
from typing import Any


def b64_encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def b64_decode(data_b64: str) -> bytes:
    return base64.b64decode(data_b64.encode("ascii"))


def ensure_type(msg: dict[str, Any]) -> str:
    msg_type = msg.get("type")
    if not isinstance(msg_type, str) or not msg_type:
        raise ValueError("Missing/invalid 'type'")
    return msg_type
