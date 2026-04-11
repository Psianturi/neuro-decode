"""NeuroDecode A2A Agent — FastAPI server.

Agent card (public):  GET  /.well-known/agent-card.json
Health check:         GET  /health
A2A endpoint (auth):  POST /   (requires X-API-Key header, enforced by middleware)
"""
import asyncio
import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse

load_dotenv()

from middleware import ApiKeyMiddleware, load_api_keys  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_RETRYABLE_MARKERS = ("503", "429", "unavailable", "overloaded", "resource exhausted")


def _is_retryable_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(marker in msg for marker in _RETRYABLE_MARKERS)


def _preferred_language_hint(text: str) -> str:
    lower = f" {text.lower()} "
    id_markers = (
        " saya ", " anak ", " tidak ", " nggak ", " ga ", " bagaimana ",
        " tolong ", " dengan ", " dan ", " kalau ", " mau ", " bisa "
    )
    if any(marker in lower for marker in id_markers):
        return "Indonesian"
    return "English"


def _build_task_result(task_id: str, context_id: str, response_text: str) -> dict:
    artifact_part = {
        "type": "text",
        "kind": "text",
        "text": response_text,
    }
    task = {
        "id": task_id,
        "contextId": context_id,
        "status": {"state": "completed"},
        "artifacts": [{
            "artifactId": "response-1",
            "parts": [artifact_part],
        }],
    }

    # Keep this hybrid shape intact for Prompt Opinion compatibility.
    # PO currently depends on all of the following at once:
    # - result.kind == "task"
    # - result.task wrapper present
    # - duplicated top-level task fields via **task below
    # - parts carrying both type="text" and kind="text"
    # - status.state using legacy lowercase "completed"
    # Prompt Opinion appears to require the legacy response discriminator while
    # newer A2A clients expect the wrapper member name.
    return {
        "kind": "task",
        "task": task,
        **task,
    }

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
    """A2A agent card -- A2A v1 compliant, fetched by Prompt Opinion during registration."""
    return JSONResponse({
        "name": "NeuroDecode ASD Caregiver Agent",
        "description": (
            "Real-time ASD caregiver support agent. Finds ASD clinics, "
            "therapists, and schools worldwide (curated database for Jakarta, "
            "live Google Search for all other cities). Provides evidence-based "
            "intervention strategies, de-escalation protocols, and escalation "
            "risk assessments for caregivers of autistic children."
        ),
        "version": "1.1.0",
        "provider": {
            "organization": "NeuroDecode AI",
            "url": "https://github.com/Psianturi/neuro-decode",
        },
        # Keep legacy top-level transport fields for Prompt Opinion's older
        # AgentCard parser while also serving the v1 supportedInterfaces shape.
        "url": _SERVICE_URL,
        "preferredTransport": "JSONRPC",
        "protocolVersion": "1.0",
        "supportedInterfaces": [
            {
                "url": _SERVICE_URL,
                "protocolBinding": "JSONRPC",
                "protocolVersion": "1.0",
            }
        ],
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
        },
        # Prompt Opinion currently expects an explicit type discriminator here.
        "securitySchemes": {
            "apiKey": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
                "description": "API key for NeuroDecode A2A agent access",
            }
        },
        "security": [{"apiKey": []}],
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
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
            {
                "id": "draft_therapist_handover",
                "name": "Draft Therapist Handover Note",
                "description": (
                    "Generate a structured clinical briefing note for a therapist or "
                    "psychiatrist appointment, based on caregiver's behavioral observations, "
                    "identified triggers, and effective interventions. Bridges the gap between "
                    "daily caregiver experience and clinical consultation — the 'last mile' "
                    "of ASD care coordination."
                ),
                "tags": ["ASD", "clinical", "therapist", "handover", "appointment", "FHIR-ready"],
                "examples": [
                    "Help me prepare notes for my child's therapy appointment tomorrow",
                    "Draft a handover note: child has increased meltdowns, triggers are loud noise and transitions",
                    "Create a clinical briefing based on 3 weeks of observations",
                ],
            },
            {
                "id": "assess_caregiver_wellbeing",
                "name": "Assess Caregiver Wellbeing",
                "description": (
                    "Screen caregiver stress and burnout indicators and provide personalized "
                    "self-care guidance and support resource recommendations. Addresses the "
                    "whole family system — caregiver mental health directly impacts child outcomes."
                ),
                "tags": ["ASD", "caregiver", "burnout", "wellbeing", "mental-health", "support"],
                "examples": [
                    "I've been exhausted and snapping at my child more. I need help.",
                    "Assess my stress level as a caregiver — I haven't slept properly in weeks",
                    "What support resources should I look for as an ASD caregiver?",
                ],
            },
            {
                "id": "get_sensory_diet_plan",
                "name": "Get Sensory Diet Plan",
                "description": (
                    "Generate a personalized sensory diet — a structured daily set of "
                    "sensory input activities based on occupational therapy principles — "
                    "tailored to the child's sensory profile, age, and environment. "
                    "Helps children with ASD self-regulate throughout the day."
                ),
                "tags": ["ASD", "sensory", "OT", "occupational-therapy", "regulation", "routine"],
                "examples": [
                    "My child seeks deep pressure and is sensitive to noise. Make a sensory diet.",
                    "Create a sensory regulation plan for a 7-year-old who spins and covers ears at school",
                    "Sensory diet for home use: child is hypersensitive to touch and avoids crowds",
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

        # Extract message — dual-accept: A2A v1 (field-presence) + v0.x (kind discriminator)
        params = request.get("params", {})
        message_text = ""
        if isinstance(params, dict):
            message = params.get("message", {})
            if isinstance(message, dict):
                parts = message.get("parts", [])
                for part in parts:
                    if not isinstance(part, dict):
                        continue
                    # v1 format: {"text": "..."} — field presence as discriminator
                    # v0.x format: {"kind": "text", "text": "..."}
                    if "text" in part and (part.get("kind", "text") == "text"):
                        message_text = part.get("text", "")
                        break

        if not message_text:
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {
                    "code": -32600,
                    "message": "No text content in request",
                    "data": [{
                        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
                        "reason": "INVALID_REQUEST",
                        "domain": "a2a-protocol.org",
                    }],
                },
            }

        request_id = str(request.get("id") or "")
        session_id = (
            params.get("contextId")
            or params.get("sessionId")
            or request_id
            or "default"
        )
        user_id = params.get("userId") or f"a2a-{session_id}"

        # create_session is synchronous in google-adk 0.4.0
        session = session_service.create_session(
            app_name="neurodecode_a2a",
            user_id=user_id,
            session_id=session_id,
        )

        language_hint = _preferred_language_hint(message_text)
        wrapped_text = (
            f"Reply in {language_hint} only, based on the latest user message below.\n"
            f"User message: {message_text}"
        )

        content = genai_types.Content(
            role="user",
            parts=[genai_types.Part(text=wrapped_text)],
        )

        response_text = ""
        last_fn_resp_data = None
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                response_text = ""
                last_fn_resp_data = None
                async for event in runner.run_async(
                    user_id=user_id,
                    session_id=session.id,
                    new_message=content,
                ):
                    is_final = event.is_final_response() if hasattr(event, "is_final_response") else False
                    error_code = getattr(event, "error_code", None)
                    author = getattr(event, "author", "?")

                    if hasattr(event, "content") and event.content and event.content.parts:
                        for i, part in enumerate(event.content.parts):
                            txt = getattr(part, "text", None)
                            fn_call = getattr(part, "function_call", None)
                            fn_resp = getattr(part, "function_response", None)
                            logger.info(
                                "[a2a][event] author=%s final=%s err=%s part[%d] "
                                "text=%s fn_call=%s fn_resp_keys=%s",
                                author, is_final, error_code, i,
                                repr(txt[:300]) if txt else None,
                                repr(fn_call)[:200] if fn_call else None,
                                list(fn_resp.response.keys()) if fn_resp and hasattr(fn_resp, "response") else None,
                            )
                            if txt:
                                response_text += (txt.decode("utf-8") if isinstance(txt, bytes) else str(txt))
                            if fn_resp and hasattr(fn_resp, "response"):
                                # bytes-safe: convert any non-JSON-serializable values
                                raw = fn_resp.response
                                if isinstance(raw, bytes):
                                    raw = raw.decode("utf-8", errors="replace")
                                last_fn_resp_data = raw
                    else:
                        logger.info("[a2a][event] author=%s final=%s err=%s content=None",
                                    author, is_final, error_code)
                break
            except Exception as exc:
                if _is_retryable_error(exc) and attempt < max_attempts - 1:
                    wait = 2 * (attempt + 1)
                    logger.warning(
                        "[a2a] Transient model error on attempt %d/%d: %s. Retrying in %ds",
                        attempt + 1, max_attempts, exc, wait,
                    )
                    await asyncio.sleep(wait)
                    continue
                raise

        # Fallback: if model stopped without generating text, synthesize a readable reply
        if not response_text and last_fn_resp_data is not None:
            import json as _json

            normalized = last_fn_resp_data
            if isinstance(last_fn_resp_data, dict) and isinstance(last_fn_resp_data.get("result"), str):
                try:
                    normalized = _json.loads(last_fn_resp_data["result"])
                except Exception:
                    normalized = {"result": last_fn_resp_data["result"]}

            if isinstance(normalized, dict):
                summary = str(normalized.get("summary") or "").strip()
                resources = normalized.get("resources")
                source = normalized.get("source")

                if summary:
                    response_text = summary
                elif isinstance(resources, list) and resources:
                    lines = ["Here are some ASD resources I found:"]
                    for idx, item in enumerate(resources[:5], 1):
                        if not isinstance(item, dict):
                            continue
                        name = item.get("name") or "Unknown"
                        rtype = item.get("resource_type") or "resource"
                        addr = item.get("address") or "Address not available"
                        contact = item.get("contact") or "Contact not available"
                        lines.append(f"{idx}. {name} ({rtype})")
                        lines.append(f"   Address: {addr}")
                        lines.append(f"   Contact: {contact}")
                    response_text = "\n".join(lines)
                elif source == "web_search":
                    response_text = (
                        "I could not retrieve grounded web results for that location right now. "
                        "Please try a more specific request, for example: "
                        "'Find ASD therapists in Singapore, limit 5'."
                    )
                else:
                    response_text = _json.dumps(normalized, ensure_ascii=False, default=str)
            else:
                response_text = _json.dumps(last_fn_resp_data, ensure_ascii=False, default=str)

            logger.warning("[a2a] No text response from model — using synthesized fallback")

        import json as _json_safe

        def _safe_json(obj):
            """Recursively convert bytes/unknown types for JSON serialization."""
            if isinstance(obj, bytes):
                return obj.decode("utf-8", errors="replace")
            if isinstance(obj, dict):
                return {k: _safe_json(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_safe_json(v) for v in obj]
            return obj

        safe_response_text = _safe_json(response_text) if not isinstance(response_text, str) else response_text

        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": _build_task_result(
                task_id=str(request.get("id", "task-1")),
                context_id=session_id,
                response_text=safe_response_text,
            ),
        }

    except Exception as exc:
        logger.error("[a2a] Error: %s", exc)

        # Return a user-friendly task response for transient provider overload so orchestration UIs do not fail hard on occasional 503 spikes.
        if _is_retryable_error(exc):
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "result": _build_task_result(
                    task_id=str(request.get("id", "task-1")),
                    context_id=request.get("params", {}).get("sessionId", "default"),
                    response_text=(
                        "Service is temporarily busy (high demand). "
                        "Please retry this same request in a few seconds."
                    ),
                ),
            }

        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "error": {
                "code": -32603,
                "message": "Internal agent error",
                "data": [{
                    "@type": "type.googleapis.com/google.rpc.ErrorInfo",
                    "reason": "INTERNAL_ERROR",
                    "domain": "a2a-protocol.org",
                }],
            },
        }
