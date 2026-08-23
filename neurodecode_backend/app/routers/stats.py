"""
NeuroDecode Backend — Stats & Insights Routes
=============================================
Reads from the `sessions` Firestore collection (post-crisis session summaries
written by maybe_summarize_and_notify) and aggregates into a single response
consumed by the public dashboard on neurodecode-ai website.

Endpoint:   GET /stats/summary
Proxy:      https://neurodecode-ai.vercel.app/api/proxy/stats/summary
"""

from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# ── Config ────────────────────────────────────────────────────────────────────

# Matches NEURODECODE_FIRESTORE_COLLECTION default in settings.py
COLLECTION_NAME = os.getenv("NEURODECODE_FIRESTORE_COLLECTION", "sessions")

router = APIRouter()

# ── Pydantic response models ──────────────────────────────────────────────────


class SessionStats(BaseModel):
    total_sessions: int
    avg_resolution_minutes: float
    resolution_rate: float
    active_caregivers: int
    notification_rate: float
    avg_severity: float
    follow_up_rate: float


class TriggerItem(BaseModel):
    trigger: str
    count: int
    pct: float


class SessionDataPoint(BaseModel):
    month: str
    sessions: int
    resolved: int


class ResolutionDataPoint(BaseModel):
    week: str
    avgMin: float


class InterventionItem(BaseModel):
    type: str
    success: float
    count: int


class SessionHistoryItem(BaseModel):
    id: str
    timestamp: str
    trigger: str
    resolution_time_min: float
    intervention: str
    resolved: bool
    emotion_state: str | None = None
    severity_level: int | None = None
    ai_summary: str | None = None
    caregiver_notified: bool = False


class InsightsSummary(BaseModel):
    stats: SessionStats
    triggers: list[TriggerItem]
    session_trend: list[SessionDataPoint]
    resolution_trend: list[ResolutionDataPoint]
    interventions: list[InterventionItem]
    recent_sessions: list[SessionHistoryItem]
    last_updated: str
    total_documents: int


# ── Field extraction helpers (mapped to actual session summary schema) ────────

def _get_timestamp(doc: dict[str, Any]) -> str:
    """Prefer timestamp_utc (backend schema), fallback to legacy fields."""
    for field in ("timestamp_utc", "started_at", "created_at", "timestamp"):
        val = doc.get(field)
        if val:
            if hasattr(val, "isoformat"):
                return val.isoformat()
            return str(val)
    return ""


def _get_duration_min(doc: dict[str, Any]) -> float:
    """duration_minutes is stored directly; fallback to duration_seconds / 60."""
    if isinstance(doc.get("duration_minutes"), (int, float)) and doc["duration_minutes"] > 0:
        return float(doc["duration_minutes"])
    if isinstance(doc.get("duration_seconds"), (int, float)) and doc["duration_seconds"] > 0:
        return round(doc["duration_seconds"] / 60.0, 1)
    return 0.0


def _is_resolved(doc: dict[str, Any]) -> bool:
    """Session is resolved if close_reason is 'client_close' or 'completed' (not error/idle)."""
    reason = (doc.get("close_reason") or "").lower()
    if reason in ("client_close", "completed"):
        return True
    # legacy field support
    if isinstance(doc.get("resolved"), bool):
        return doc["resolved"]
    status = (doc.get("status") or "").lower()
    return status == "resolved"


def _get_trigger(doc: dict[str, Any]) -> str:
    """
    Derive trigger from structured sub-document.
    structured.triggers_audio / structured.triggers_visual are stored as strings.
    """
    structured: dict[str, Any] = doc.get("structured") or {}
    audio = (structured.get("triggers_audio") or "").strip()
    visual = (structured.get("triggers_visual") or "").strip()

    # Prefer whichever has content; skip generic "no X triggers" placeholders
    _none_phrases = ("no trigger", "none", "no visual", "no audio", "not detected", "n/a", "")
    audio_clean = audio.lower() not in _none_phrases and len(audio) > 5
    visual_clean = visual.lower() not in _none_phrases and len(visual) > 5

    if audio_clean and visual_clean:
        return "Audio + Visual"
    if audio_clean:
        return "Audio"
    if visual_clean:
        return "Visual"

    # Fallback: check stats sub-doc
    stats: dict[str, Any] = doc.get("stats") or {}
    if stats.get("audio_trigger_count", 0) > 0 and stats.get("visual_trigger_count", 0) > 0:
        return "Audio + Visual"
    if stats.get("audio_trigger_count", 0) > 0:
        return "Audio"
    if stats.get("visual_trigger_count", 0) > 0:
        return "Visual"
    return "Unknown"


def _get_agent_actions(doc: dict[str, Any]) -> str:
    """Return primary agent action from structured.agent_actions."""
    structured: dict[str, Any] = doc.get("structured") or {}
    actions = (structured.get("agent_actions") or "").strip()
    if actions and len(actions) > 5:
        # Truncate to first sentence for display
        first = actions.split(".")[0].strip()
        return first[:80] if first else "AI Guidance"
    return "AI Guidance"


def _get_specialist_guidance(doc: dict[str, Any]) -> str:
    structured: dict[str, Any] = doc.get("structured") or {}
    sg = (structured.get("specialist_guidance") or "").strip()
    _none_phrases = ("no external", "none", "not used", "n/a", "")
    if sg.lower() not in _none_phrases and len(sg) > 5:
        return sg
    return ""


def _is_caregiver_notified(doc: dict[str, Any]) -> bool:
    # push_sent is not stored in session summary directly, but notification
    # existence is implied by close_reason + notification rule firing.
    # We use caregiver_notified if present, otherwise default False.
    if isinstance(doc.get("caregiver_notified"), bool):
        return doc["caregiver_notified"]
    if isinstance(doc.get("push_sent"), bool):
        return doc["push_sent"]
    return False


# ── Route: GET /stats/summary ─────────────────────────────────────────────────


@router.get("/summary", response_model=InsightsSummary)
async def get_stats_summary(limit: int = 500) -> InsightsSummary:
    """
    Aggregate stats from the `sessions` Firestore collection.
    Called by the public dashboard proxy at /api/proxy/stats/summary.
    """
    # Import here to avoid circular import at module load time
    from app.session_store import SessionStore  # noqa: PLC0415
    from app.settings import get_settings  # noqa: PLC0415

    settings = get_settings()
    if not settings.firestore_enabled:
        raise HTTPException(status_code=503, detail="Firestore not enabled on this instance")

    try:
        from google.cloud import firestore as _fs  # noqa: PLC0415
        db = _fs.Client(project=settings.firestore_project)
        docs_ref = (
            db.collection(COLLECTION_NAME)
            .order_by("timestamp_utc", direction=_fs.Query.DESCENDING)
            .limit(limit)
        )
        docs_snapshot = docs_ref.get()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Firestore unavailable: {exc}") from exc

    sessions: list[dict[str, Any]] = []
    for doc in docs_snapshot:
        data = doc.to_dict() or {}
        data["_doc_id"] = doc.id
        # Serialise Firestore DatetimeWithNanoseconds → ISO string
        for key, val in data.items():
            if hasattr(val, "isoformat"):
                data[key] = val.isoformat()
        sessions.append(data)

    total = len(sessions)
    if total == 0:
        _empty = SessionStats(
            total_sessions=0,
            avg_resolution_minutes=0.0,
            resolution_rate=0.0,
            active_caregivers=0,
            notification_rate=0.0,
            avg_severity=0.0,
            follow_up_rate=0.0,
        )
        return InsightsSummary(
            stats=_empty,
            triggers=[],
            session_trend=[],
            resolution_trend=[],
            interventions=[],
            recent_sessions=[],
            last_updated=datetime.now(timezone.utc).isoformat(),
            total_documents=0,
        )

    # ── Aggregate stats ───────────────────────────────────────────────────────
    resolved_count = sum(1 for s in sessions if _is_resolved(s))
    resolution_rate = round(resolved_count / total * 100, 1)

    durations = [_get_duration_min(s) for s in sessions]
    valid_durations = [d for d in durations if d > 0]
    avg_resolution_minutes = round(sum(valid_durations) / len(valid_durations), 1) if valid_durations else 0.0

    unique_users = {
        s.get("user_id") or s.get("profile_id")
        for s in sessions
        if s.get("user_id") or s.get("profile_id")
    }
    active_caregivers = len(unique_users)

    notified_count = sum(1 for s in sessions if _is_caregiver_notified(s))
    notification_rate = round(notified_count / total * 100, 1)

    # Severity: not directly stored — derive from trigger counts as proxy
    avg_severity = 0.0  # reserved for future severity_level field

    follow_up_rate = 0.0  # reserved for future follow_up_required field

    stats = SessionStats(
        total_sessions=total,
        avg_resolution_minutes=avg_resolution_minutes,
        resolution_rate=resolution_rate,
        active_caregivers=active_caregivers,
        notification_rate=notification_rate,
        avg_severity=avg_severity,
        follow_up_rate=follow_up_rate,
    )

    # ── Triggers ──────────────────────────────────────────────────────────────
    trigger_counts: dict[str, int] = defaultdict(int)
    for s in sessions:
        trigger_counts[_get_trigger(s)] += 1
    triggers = [
        TriggerItem(trigger=t, count=c, pct=round(c / total * 100, 1))
        for t, c in sorted(trigger_counts.items(), key=lambda x: -x[1])[:6]
    ]

    # ── Session trend (by month) ───────────────────────────────────────────────
    month_data: dict[str, dict[str, int]] = defaultdict(lambda: {"sessions": 0, "resolved": 0})
    for s in sessions:
        ts = _get_timestamp(s)
        if not ts:
            continue
        try:
            d = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            key = d.strftime("%b '%y")
            month_data[key]["sessions"] += 1
            if _is_resolved(s):
                month_data[key]["resolved"] += 1
        except Exception:
            continue

    session_trend = [
        SessionDataPoint(month=k, sessions=v["sessions"], resolved=v["resolved"])
        for k, v in sorted(month_data.items(), key=lambda x: datetime.strptime(x[0], "%b '%y"))
    ]

    # ── Resolution trend (by week) ────────────────────────────────────────────
    week_data: dict[str, list[float]] = defaultdict(list)
    for s in sessions:
        ts = _get_timestamp(s)
        if not ts:
            continue
        try:
            d = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            week_num = d.isocalendar()[1]
            key = f"W{week_num}"
            dur = _get_duration_min(s)
            if dur > 0:
                week_data[key].append(dur)
        except Exception:
            continue

    resolution_trend = [
        ResolutionDataPoint(week=k, avgMin=round(sum(v) / len(v), 1))
        for k, v in sorted(week_data.items(), key=lambda x: int(x[0][1:]))
    ]

    # ── Interventions (from agent_actions field) ───────────────────────────────
    intervention_data: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "resolved": 0})
    for s in sessions:
        itype = _get_agent_actions(s)
        intervention_data[itype]["total"] += 1
        if _is_resolved(s):
            intervention_data[itype]["resolved"] += 1

    interventions = [
        InterventionItem(
            type=t,
            count=v["total"],
            success=round(v["resolved"] / v["total"] * 100, 1) if v["total"] else 0.0,
        )
        for t, v in sorted(intervention_data.items(), key=lambda x: -x[1]["total"])[:5]
    ]

    # ── Recent sessions ───────────────────────────────────────────────────────
    sorted_sessions = sorted(
        [s for s in sessions if _get_timestamp(s)],
        key=_get_timestamp,
        reverse=True,
    )[:10]

    recent_sessions = [
        SessionHistoryItem(
            id=str(s.get("_doc_id") or s.get("session_id") or ""),
            timestamp=_get_timestamp(s),
            trigger=_get_trigger(s),
            resolution_time_min=_get_duration_min(s),
            intervention=_get_agent_actions(s),
            resolved=_is_resolved(s),
            emotion_state=None,
            severity_level=None,
            ai_summary=(s.get("structured") or {}).get("title") or s.get("summary_text"),
            caregiver_notified=_is_caregiver_notified(s),
        )
        for s in sorted_sessions
    ]

    return InsightsSummary(
        stats=stats,
        triggers=triggers,
        session_trend=session_trend,
        resolution_trend=resolution_trend,
        interventions=interventions,
        recent_sessions=recent_sessions,
        last_updated=datetime.now(timezone.utc).isoformat(),
        total_documents=total,
    )
