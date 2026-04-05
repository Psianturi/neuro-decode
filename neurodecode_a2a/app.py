"""NeuroDecode A2A Agent — FastAPI server.

Agent card (public):  GET  /.well-known/agent-card.json
Health check:         GET  /health
A2A endpoint (auth):  POST /   (requires X-API-Key header, enforced by middleware)
"""
from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse

load_dotenv()

from middleware import ApiKeyMiddleware, load_api_keys  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="NeuroDecode A2A Agent")
app.add_middleware(ApiKeyMiddleware)

_SERVICE_URL = os.getenv(
    "A2A_SERVICE_URL",
    "https://neurodecode-a2a-jzfv6ygw3q-as.a.run.app",
)


@app.on_event("startup")
async def startup() -> None:
    load_api_keys()
    logger.info("[startup] NeuroDecode A2A Agent ready -- %s", _SERVICE_URL)


@app.get("/.well-known/agent-card.json", include_in_schema=False)
async def agent_card() -> JSONResponse:
    """A2A agent card -- fetched by Prompt Opinion during registration."""
    return JSONResponse({
        "name": "NeuroDecode ASD Caregiver Agent",
        "description": (
            "Real-time ASD caregiver support agent. Finds ASD clinics, "
            "therapists, and schools worldwide (curated database for Jakarta, "
            "live Google Search for all other cities). Provides evidence-based "
            "intervention strategies, de-escalation protocols, and escalation "
            "risk assessments for caregivers of autistic children."
        ),
        "url": _SERVICE_URL,
        "version": "1.0.0",
        "protocolVersion": "0.2.2",
        "preferredTransport": "JSONRPC",
        "provider": {
            "organization": "NeuroDecode AI",
            "url": "https://github.com/Psianturi/neuro-decode",
        },
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
            "stateTransitionHistory": False,
        },
        "authentication": {
            "schemes": ["ApiKey"],
        },
        "defaultInputModes": ["text"],
        "defaultOutputModes": ["text"],
        "skills": [
            {
                "id": "find_asd_resources",
                "name": "Find ASD Resources",
                "description": (
                    "Find ASD-relevant clinics, therapists, inclusive schools, "
                    "hospitals, and community centers worldwide. "
                    "Jakarta / Indonesia: returns 198 curated verified resources. "
                    "All other cities: live Google Search via Gemini."
                ),
                "tags": ["ASD", "resources", "global", "clinic", "therapist", "Jakarta"],
                "examples": [
                    "Find ASD therapists in London",
                    "Cari klinik autis di Jakarta",
                    "Show me inclusive schools in Singapore",
                    "ASD support groups in Sydney",
                ],
            },
            {
                "id": "suggest_interventions",
                "name": "Suggest ASD Interventions",
                "description": (
                    "Get evidence-based intervention strategies for a specific "
                    "ASD trigger type, tailored to child age and sensory profile."
                ),
                "tags": ["ASD", "intervention", "trigger", "strategy"],
                "examples": [
                    "What should I do when my child has a meltdown from loud noise?",
                    "Suggest interventions for a child who gets distressed by transitions",
                ],
            },
            {
                "id": "get_de_escalation_steps",
                "name": "De-escalation Protocol",
                "description": (
                    "Get step-by-step de-escalation protocol for an active "
                    "distress situation, with urgency-appropriate guidance."
                ),
                "tags": ["ASD", "de-escalation", "meltdown", "crisis"],
                "examples": [
                    "My child is having a meltdown right now, what do I do?",
                    "Child is screaming and hitting walls, need immediate help",
                ],
            },
            {
                "id": "assess_escalation_risk",
                "name": "Assess Escalation Risk",
                "description": (
                    "Assess escalation risk level (low/medium/high/critical) "
                    "from behavioral pattern descriptions. Simulates NeuroDecode "
                    "observer model reasoning in natural language."
                ),
                "tags": ["ASD", "risk", "assessment", "behavior", "observer"],
                "examples": [
                    "Child has been rocking and vocalizing for 10 minutes, assess risk",
                    "Evaluate escalation risk: high-pitched sounds, covering ears",
                ],
            },
        ],
    })


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "agent": "neurodecode-a2a"}


@app.post("/")
async def a2a_endpoint(request: dict) -> dict:
    """Main A2A JSON-RPC endpoint. API key enforced by ApiKeyMiddleware."""
    try:
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types as genai_types
        from agent import root_agent

        session_service = InMemorySessionService()
        runner = Runner(
            agent=root_agent,
            app_name="neurodecode_a2a",
            session_service=session_service,
        )

        # Extract message from A2A JSON-RPC request format
        params = request.get("params", {})
        message_text = ""
        if isinstance(params, dict):
            message = params.get("message", {})
            if isinstance(message, dict):
                parts = message.get("parts", [])
                for part in parts:
                    if isinstance(part, dict) and part.get("kind") == "text":
                        message_text = part.get("text", "")
                        break

        if not message_text:
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {"code": -32600, "message": "No text content in request"},
            }

        session_id = params.get("sessionId", "default")
        user_id = params.get("userId", "a2a-user")

        # create_session is synchronous in google-adk 0.4.0
        session = session_service.create_session(
            app_name="neurodecode_a2a",
            user_id=user_id,
            session_id=session_id,
        )

        content = genai_types.Content(
            role="user",
            parts=[genai_types.Part(text=message_text)],
        )

        response_text = ""
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=content,
        ):
            if event.is_final_response() and event.content:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        response_text += part.text

        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": {
                "id": request.get("id", "task-1"),
                "status": {"state": "completed"},
                "artifacts": [{
                    "parts": [{"kind": "text", "text": response_text}]
                }],
            },
        }

    except Exception as exc:
        logger.error("[a2a] Error: %s", exc)
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "error": {"code": -32603, "message": str(exc)},
        }
