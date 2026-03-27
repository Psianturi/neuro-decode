"""
Pydantic message models passed between agents in the pipeline.

All data flowing through the pipeline is anonymized at the SessionObserverAgent
boundary — no raw user_id, profile_id, child names, or caregiver names ever
leave SessionContext.
"""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel


class SessionContext(BaseModel):
    """
    Aggregated, anonymized summary of recent live sessions.
    Produced by SessionObserverAgent. Safe to pass to Gemini prompts.
    """
    session_count: int
    hours_window: int  # how many hours back we looked
    # Aggregated trigger patterns — no PII
    audio_trigger_patterns: list[str]   # e.g. ["loud sudden noise", "TV volume"]
    visual_trigger_patterns: list[str]  # e.g. ["crowded room", "flickering light"]
    common_follow_ups: list[str]        # e.g. ["reduce noise", "deep pressure"]
    # Dominant topic hint for post generation
    dominant_topic_hint: str | None     # e.g. "sensory overload during mealtimes"
    has_data: bool                      # False if Firestore unavailable or no sessions


class CommunityInsight(BaseModel):
    """
    A distilled, community-shareable insight produced by InsightAgent.
    Derived from SessionContext — never contains raw session data.
    """
    topic: str              # e.g. "sensory overload during mealtimes"
    angle: str              # e.g. "why transition times are the hidden trigger"
    evidence_summary: str   # anonymized aggregate, e.g. "patterns observed across recent sessions"
    suggested_submolt: str  # e.g. "general", "todayilearned"
    persona_key: str        # which persona from PersonaRegistry to use


class DraftContent(BaseModel):
    """Post draft produced by MoltbookDraftAgent."""
    title: str
    body: str
    submolt: str
    persona_key: str
    insight: CommunityInsight


class ReviewVerdict(BaseModel):
    """Quality gate result from ReviewAgent."""
    approved: bool
    reason: str
    revised_title: str | None = None  # if reviewer suggests a tweak
    revised_body: str | None = None


class AgentMessage(BaseModel):
    """
    Audit trail record written to Firestore agent_messages/ (optional).
    Mirrors the ed-donner pattern: every agent-to-agent handoff is logged.
    """
    from_agent: str
    to_agent: str
    message_type: str
    summary: str            # short human-readable description of what was passed
    timestamp_utc: str
