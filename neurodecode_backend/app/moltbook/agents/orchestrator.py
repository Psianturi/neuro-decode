"""
AgentOrchestrator

Runs the multi-agent pipeline each heartbeat cycle:

  SessionObserverAgent  →  CreatorAgent  →  (used by heartbeat for post generation)
                                         →  ReviewAgent  (post-draft quality gate)

The orchestrator is the only entry point called from heartbeat.py.
It returns a PipelineContext that heartbeat uses to:
  1. Override the post topic with a context-derived CommunityInsight
  2. Pass persona system addendum to generate_post()
  3. Pass the ReviewAgent for post-draft verification

Audit trail: if Firestore is available, each agent handoff is logged to
agent_messages/ collection (non-blocking, best-effort).
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.moltbook.agents.creator import PERSONA_REGISTRY, CreatorAgent
from app.moltbook.agents.messages import (
    AgentMessage,
    CommunityInsight,
    DraftContent,
    ReviewVerdict,
    SessionContext,
)
from app.moltbook.agents.review import ReviewAgent
from app.moltbook.agents.session_observer import SessionObserverAgent

logger = logging.getLogger(__name__)


@dataclass
class PipelineContext:
    """
    Result of one orchestrator run. Passed to heartbeat.py so it can
    enrich post generation with real session context.
    """
    session_ctx: SessionContext
    insight: CommunityInsight | None
    persona_system_addendum: str
    review_agent: ReviewAgent
    errors: list[str] = field(default_factory=list)


class AgentOrchestrator:
    """
    Coordinates all agents in the pipeline.
    Instantiated once per heartbeat cycle (stateless between cycles).
    """

    def __init__(
        self,
        *,
        model: str,
        firestore_project: str | None,
        sessions_collection: str,
        agent_messages_collection: str = "agent_messages",
        persist_audit: bool = False,
    ) -> None:
        self._model = model
        self._persist_audit = persist_audit
        self._agent_messages_collection = agent_messages_collection
        self._fs_project = firestore_project

        self._observer = SessionObserverAgent(
            firestore_project=firestore_project,
            sessions_collection=sessions_collection,
        )
        self._creator = CreatorAgent(model=model)
        self._reviewer = ReviewAgent(model=model)

    async def run_context_pipeline(self) -> PipelineContext:
        """
        Run SessionObserver → Creator.
        Returns PipelineContext for heartbeat to use during post generation.
        """
        errors: list[str] = []

        # Step 1: Observe sessions
        try:
            session_ctx: SessionContext = await self._observer.run()
            await self._audit("SessionObserver", "Creator", "SessionContext", session_ctx)
        except Exception as exc:
            logger.warning("[Orchestrator] SessionObserver failed: %s", exc)
            errors.append(f"observer: {exc}")
            session_ctx = SessionContext(
                session_count=0,
                hours_window=48,
                audio_trigger_patterns=[],
                visual_trigger_patterns=[],
                common_follow_ups=[],
                dominant_topic_hint=None,
                has_data=False,
            )

        # Step 2: Creator selects persona + derives insight
        insight: CommunityInsight | None = None
        persona_addendum = ""
        try:
            insight = await self._creator.run(session_ctx)
            await self._audit("Creator", "Heartbeat", "CommunityInsight", insight)
            persona_addendum = PERSONA_REGISTRY[insight.persona_key]["system_addendum"]
        except Exception as exc:
            logger.warning("[Orchestrator] Creator failed: %s", exc)
            errors.append(f"creator: {exc}")

        logger.warning(
            "[Orchestrator] Pipeline done — has_data=%s insight_topic=%s persona=%s errors=%d",
            session_ctx.has_data,
            insight.topic if insight else "none",
            insight.persona_key if insight else "none",
            len(errors),
        )

        return PipelineContext(
            session_ctx=session_ctx,
            insight=insight,
            persona_system_addendum=persona_addendum,
            review_agent=self._reviewer,
            errors=errors,
        )

    async def review_draft(
        self,
        *,
        pipeline_ctx: PipelineContext,
        title: str,
        body: str,
        submolt: str,
    ) -> ReviewVerdict:
        """
        Run ReviewAgent on a draft post. Called from heartbeat after generate_post().
        Returns ReviewVerdict — heartbeat decides whether to publish.
        """
        if pipeline_ctx.insight is None:
            # No insight context — skip review, auto-approve
            return ReviewVerdict(approved=True, reason="no insight context, auto-approved")

        draft = DraftContent(
            title=title,
            body=body,
            submolt=submolt,
            persona_key=pipeline_ctx.insight.persona_key,
            insight=pipeline_ctx.insight,
        )
        try:
            verdict = await self._reviewer.run(draft)
            await self._audit("Heartbeat", "Review", "DraftContent", draft)
            await self._audit("Review", "Heartbeat", "ReviewVerdict", verdict)
            return verdict
        except Exception as exc:
            logger.warning("[Orchestrator] ReviewAgent failed: %s", exc)
            return ReviewVerdict(approved=True, reason=f"review error: {exc}, auto-approved")

    async def _audit(
        self,
        from_agent: str,
        to_agent: str,
        message_type: str,
        payload: Any,
    ) -> None:
        """Write agent handoff to Firestore agent_messages/ (best-effort, non-blocking)."""
        if not self._persist_audit:
            return
        try:
            summary = _summarize(payload)
            record = AgentMessage(
                from_agent=from_agent,
                to_agent=to_agent,
                message_type=message_type,
                summary=summary,
                timestamp_utc=datetime.now(timezone.utc).isoformat(),
            ).model_dump()
            await asyncio.to_thread(self._write_audit, record)
        except Exception as exc:
            logger.debug("[Orchestrator] Audit write failed (non-critical): %s", exc)

    def _write_audit(self, record: dict) -> None:
        try:
            from google.cloud import firestore  # type: ignore
            client = firestore.Client(project=self._fs_project)
            client.collection(self._agent_messages_collection).add(record)
        except Exception as exc:
            logger.debug("[Orchestrator] Firestore audit write: %s", exc)


def _summarize(payload: Any) -> str:
    if hasattr(payload, "model_dump"):
        d = payload.model_dump()
        # Return first 2 fields as summary
        parts = [f"{k}={str(v)[:60]}" for k, v in list(d.items())[:2]]
        return ", ".join(parts)
    return str(payload)[:120]
