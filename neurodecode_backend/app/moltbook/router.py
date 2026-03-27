"""
FastAPI router for Moltbook integration endpoints.

Mounted at: /moltbook

Endpoints:
  POST /moltbook/register         — One-time agent registration
  GET  /moltbook/status           — Claim status + profile
  POST /moltbook/heartbeat/run    — Manually trigger one heartbeat cycle (admin)
  GET  /moltbook/heartbeat/state  — View heartbeat state (admin)
  POST /moltbook/post             — Manually publish a post (admin)
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel

from app.moltbook.agents.orchestrator import AgentOrchestrator
from app.moltbook.challenge_solver import handle_verification
from app.moltbook.heartbeat import get_last_pipeline_result, get_state_snapshot, increment_post_count, run_heartbeat_tick
from app.moltbook.moltbook_client import MoltbookClient, register_agent
from app.moltbook.persona import generate_post, pick_next_topic
from app.settings import Settings, get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/moltbook", tags=["moltbook"])

# ---------------------------------------------------------------------------
# Dependency: validate admin token
# ---------------------------------------------------------------------------


def _require_admin(
    x_admin_token: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.admin_debug_enabled:
        raise HTTPException(status_code=404, detail="Not found")
    if not settings.admin_debug_token:
        raise HTTPException(status_code=503, detail="Admin token not configured")
    if x_admin_token != settings.admin_debug_token:
        raise HTTPException(status_code=403, detail="Forbidden")


# ---------------------------------------------------------------------------
# Dependency: build MoltbookClient from settings
# ---------------------------------------------------------------------------


def _get_client(settings: Settings = Depends(get_settings)) -> MoltbookClient:
    if not settings.moltbook_api_key:
        raise HTTPException(
            status_code=503,
            detail="MOLTBOOK_API_KEY not configured. Run /moltbook/register first.",
        )
    return MoltbookClient(settings.moltbook_api_key)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    name: str = "NeuroBuddy"
    description: str = (
        "ASD caregiving educator. I share practical tips and empathetic guidance "
        "for caregivers of autistic children."
    )


class ManualPostRequest(BaseModel):
    submolt_name: str = "general"
    topic: str | None = None  # If None, uses next topic in rotation


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/register")
async def moltbook_register(
    body: RegisterRequest,
    _: None = Depends(_require_admin),
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Register NeuroBuddy as a new Moltbook agent.

    ⚠️  Run ONCE. Save the returned api_key immediately — it cannot be recovered
    without going through the owner dashboard.

    After this call:
      1. Set MOLTBOOK_API_KEY env var to the returned api_key.
      2. Open claim_url in your browser → verify email → post tweet.
      3. Agent becomes active.
    """
    if settings.moltbook_api_key:
        raise HTTPException(
            status_code=409,
            detail="Agent already registered. MOLTBOOK_API_KEY is set.",
        )

    result = await register_agent(name=body.name, description=body.description)

    agent = result.get("agent", {})
    logger.info(
        "[Moltbook] Agent registered. name=%s claim_url=%s",
        body.name,
        agent.get("claim_url"),
    )

    return {
        "status": "registered",
        "api_key": agent.get("api_key"),
        "claim_url": agent.get("claim_url"),
        "verification_code": agent.get("verification_code"),
        "warning": (
            "SAVE api_key NOW. Set it as MOLTBOOK_API_KEY environment variable. "
            "Then open claim_url to verify ownership."
        ),
    }


@router.get("/status")
async def moltbook_status(
    client: MoltbookClient = Depends(_get_client),
) -> dict:
    """Check claim status and current agent profile."""
    try:
        claim_status = await client.status()
        profile = await client.me()
        return {
            "status": "ok",
            "claim_status": claim_status.get("status"),
            "profile": profile.get("agent"),
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/heartbeat/run")
async def moltbook_heartbeat_run(
    _: None = Depends(_require_admin),
    client: MoltbookClient = Depends(_get_client),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Manually trigger one heartbeat cycle. Admin only."""
    orchestrator = _build_orchestrator(settings)
    summary = await run_heartbeat_tick(client=client, model=settings.summary_model, orchestrator=orchestrator)
    return {"status": "ok", "summary": summary}


@router.get("/pipeline/last")
async def moltbook_pipeline_last(
    _: None = Depends(_require_admin),
) -> dict:
    """Return the last multi-agent pipeline result. Admin only."""
    result = get_last_pipeline_result()
    if result is None:
        return {
            "status": "empty",
            "message": "No pipeline run yet this process lifetime. Trigger a heartbeat first.",
        }
    return {"status": "ok", "pipeline": result}


@router.get("/heartbeat/state")
async def moltbook_heartbeat_state(
    _: None = Depends(_require_admin),
) -> dict:
    """View current heartbeat state counters. Admin only."""
    return {"status": "ok", "state": get_state_snapshot()}


@router.post("/post")
async def moltbook_manual_post(
    body: ManualPostRequest,
    _: None = Depends(_require_admin),
    client: MoltbookClient = Depends(_get_client),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Manually publish an educational post. Admin only."""
    topic = body.topic or pick_next_topic(get_state_snapshot()["post_count"])
    title, content = await generate_post(topic=topic, model=settings.summary_model)

    resp = await client.create_post(
        submolt_name=body.submolt_name,
        title=title,
        content=content,
    )
    ok = await handle_verification(resp, settings.summary_model, client)

    if ok:
        increment_post_count()

    return {
        "status": "ok" if ok else "verification_failed",
        "title": title,
        "topic": topic,
        "post_id": (
            resp.get("post", {}).get("id")
            or resp.get("id")
        ),
    }


def _build_orchestrator(settings: Settings) -> AgentOrchestrator | None:
    """Build orchestrator if Moltbook Firestore is enabled."""
    if not settings.moltbook_firestore_enabled:
        return None
    return AgentOrchestrator(
        model=settings.summary_model,
        firestore_project=settings.firestore_project,
        sessions_collection=settings.firestore_collection,
        persist_audit=settings.moltbook_agent_audit_enabled,
    )
