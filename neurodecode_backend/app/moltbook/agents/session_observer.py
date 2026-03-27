"""
SessionObserverAgent

Reads recent live sessions from Firestore (last 48h), aggregates trigger
patterns, and produces a fully anonymized SessionContext.

PRIVACY CONTRACT:
  - No user_id, profile_id, child name, or caregiver name leaves this agent.
  - Only aggregate patterns (e.g. "loud noise", "crowded room") are forwarded.
  - If Firestore is unavailable, returns SessionContext(has_data=False).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.moltbook.agents.base import BaseAgent
from app.moltbook.agents.messages import SessionContext

logger = logging.getLogger(__name__)

_OBSERVE_WINDOW_HOURS = 48
_MAX_SESSIONS = 20


def _is_meaningful(text: str) -> bool:
    if not text:
        return False
    weak = ("no strong", "no trigger", "not detected", "no visual", "no audio", "-")
    return not any(w in text.lower() for w in weak)


def _dedupe(items: list[str], limit: int = 5) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(item.strip())
        if len(out) >= limit:
            break
    return out


class SessionObserverAgent(BaseAgent):
    """
    Reads Firestore sessions collection and produces anonymized SessionContext.
    Falls back to SessionContext(has_data=False) if Firestore is unavailable.
    """

    def __init__(
        self,
        *,
        firestore_project: str | None,
        sessions_collection: str,
    ) -> None:
        super().__init__("SessionObserver")
        self._project = firestore_project
        self._collection = sessions_collection
        self._fs_client: Any | None = None

    def _get_client(self) -> Any | None:
        try:
            from google.cloud import firestore  # type: ignore
            if self._fs_client is None:
                self._fs_client = firestore.Client(project=self._project)
            return self._fs_client
        except Exception as exc:
            self.warn("Firestore client unavailable: %s", exc)
            return None

    def _fetch_recent_sessions(self) -> list[dict]:
        client = self._get_client()
        if client is None:
            return []

        from google.cloud import firestore  # type: ignore

        cutoff = (
            datetime.now(timezone.utc) - timedelta(hours=_OBSERVE_WINDOW_HOURS)
        ).isoformat()

        try:
            query = (
                client.collection(self._collection)
                .where("timestamp_utc", ">=", cutoff)
                .order_by("timestamp_utc", direction=firestore.Query.DESCENDING)
                .limit(_MAX_SESSIONS)
            )
            return [dict(doc.to_dict() or {}) for doc in query.stream()]
        except Exception as exc:
            self.warn("Firestore query failed: %s", exc)
            return []

    def _aggregate(self, sessions: list[dict]) -> SessionContext:
        audio_triggers: list[str] = []
        visual_triggers: list[str] = []
        follow_ups: list[str] = []

        for s in sessions:
            structured = s.get("structured") or {}
            audio = str(structured.get("triggers_audio") or "")
            visual = str(structured.get("triggers_visual") or "")
            follow = str(structured.get("follow_up") or "")

            if _is_meaningful(audio):
                audio_triggers.append(audio)
            if _is_meaningful(visual):
                visual_triggers.append(visual)
            if _is_meaningful(follow):
                follow_ups.append(follow)

        # Derive dominant topic hint from most common trigger type
        dominant: str | None = None
        if audio_triggers and len(audio_triggers) >= len(visual_triggers):
            dominant = f"audio sensory triggers: {audio_triggers[0]}"
        elif visual_triggers:
            dominant = f"visual sensory triggers: {visual_triggers[0]}"

        return SessionContext(
            session_count=len(sessions),
            hours_window=_OBSERVE_WINDOW_HOURS,
            audio_trigger_patterns=_dedupe(audio_triggers),
            visual_trigger_patterns=_dedupe(visual_triggers),
            common_follow_ups=_dedupe(follow_ups),
            dominant_topic_hint=dominant,
            has_data=bool(sessions),
        )

    async def run(self, message: None = None) -> SessionContext:
        self.log("Observing sessions from last %dh", _OBSERVE_WINDOW_HOURS)
        sessions = await asyncio.to_thread(self._fetch_recent_sessions)
        ctx = self._aggregate(sessions)
        self.log(
            "Observed %d sessions — audio_patterns=%d visual_patterns=%d",
            ctx.session_count,
            len(ctx.audio_trigger_patterns),
            len(ctx.visual_trigger_patterns),
        )
        return ctx
