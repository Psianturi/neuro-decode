"""A2A Skill Client — non-blocking HTTP client for neurodecode-a2a service.

Called from the live WebSocket session to enrich Gemini Live context with
specialist clinical skills. All calls have a hard timeout and fail-open:
if the A2A service is unavailable or slow, the live session continues
normally without any degradation.

Protocol: JSON-RPC 2.0 over HTTP POST (Google ADK A2A specification).
Response text is extracted from result.status.message.parts[0].text.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_SECONDS = 4.0
_MAX_RESULT_CHARS = 500


async def call_skill(
    *,
    a2a_url: str,
    prompt: str,
    api_key: str | None = None,
    timeout: float = _DEFAULT_TIMEOUT_SECONDS,
) -> str | None:
    """Send a natural-language prompt to the A2A agent and return its response text.

    The prompt should describe the clinical situation in plain language. The A2A
    agent will route internally to the correct skill (e.g. assess_escalation_risk,
    get_de_escalation_steps) based on the content.

    Returns:
        The agent's text response (capped at _MAX_RESULT_CHARS), or None on any
        error. Callers MUST treat None as a normal no-op (fail-open contract).
    """
    if not a2a_url:
        return None

    task_id = uuid.uuid4().hex
    payload: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": task_id,
        "method": "tasks/send",
        "params": {
            "id": task_id,
            "message": {
                "role": "user",
                "parts": [{"text": prompt}],
            },
        },
    }

    try:
        req_headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            req_headers["X-API-Key"] = api_key

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                a2a_url,
                json=payload,
                headers=req_headers,
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()

        result: dict[str, Any] = data.get("result") or {}

        # Primary path: result.status.message.parts[0].text (ADK synchronous response)
        status: dict[str, Any] = result.get("status") or {}
        message: dict[str, Any] = status.get("message") or {}
        parts: list[Any] = message.get("parts") or []
        if parts:
            text = str((parts[0] or {}).get("text") or "").strip()
            if text:
                return text[:_MAX_RESULT_CHARS]

        # Fallback: result.artifacts[0].parts[0].text (ADK artifact response)
        artifacts: list[Any] = result.get("artifacts") or []
        if artifacts:
            artifact_parts: list[Any] = (artifacts[0] or {}).get("parts") or []
            if artifact_parts:
                text = str((artifact_parts[0] or {}).get("text") or "").strip()
                if text:
                    return text[:_MAX_RESULT_CHARS]

        logger.debug("[a2a_client] Response parsed but no text found in result")
        return None

    except httpx.TimeoutException:
        logger.debug("[a2a_client] Skill call timed out after %.1fs (fail-open)", timeout)
        return None
    except Exception as exc:
        logger.debug("[a2a_client] Skill call failed (fail-open): %s", exc)
        return None
