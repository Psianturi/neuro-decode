from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import datetime, timezone
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from google import genai

from app.ai_processor import ai_engine
from app.gemini_live import GeminiLiveSession
from app.memory_context import build_private_memory_context
from app.profile_store import ProfileStore
from app.protocol import b64_decode, b64_encode, ensure_type
from app.session_store import SessionStore
from app.settings import get_settings


load_dotenv()

app = FastAPI(title="NeuroDecode AI Backend")

IDLE_TIMEOUT_SECONDS = 120
AUDIO_OBSERVER_COOLDOWN_SECONDS = 6
VISION_OBSERVER_COOLDOWN_SECONDS = 4
MIN_AUDIO_BYTES_FOR_ANALYSIS = 32000  # ~1s of 16kHz mono PCM16
LATEST_SESSION_MAX_ITEMS = 10


@app.on_event("startup")
async def warm_observer_models() -> None:
    ai_engine.start_background_warmup()


SYSTEM_INSTRUCTION = (
    "You are NeuroDecode AI, an empathetic real-time decision-support assistant for "
    "caregivers supporting autistic children. You do NOT diagnose or provide medical "
    "advice. You will sometimes receive hidden internal sensor notes formatted as "
    "[Visual Observer Note] or [Audio Observer Note]. Treat these notes as private "
    "context only. NEVER read or quote the note text verbatim to the caregiver. "
    "Instead, translate it into natural, calm, practical support guidance. Prioritize "
    "short, supportive interventions such as reducing sensory load, grounding, "
    "co-regulation, deep pressure when appropriate, and clear step-by-step caregiver "
    "actions. Ask one clarifying question if uncertainty is high. If there is risk of "
    "harm, advise immediate professional or emergency help. Keep responses concise, "
    "supportive, and non-judgmental. Mirror the caregiver's language automatically: "
    "if they speak Indonesian, reply in natural Indonesian; if they speak English, "
    "reply in English. Prefer spoken responses that are 1-2 short sentences unless "
    "more detail is clearly needed. Do not give a long self-introduction or repeat "
    "your role unless the caregiver asks. Never say the phrases [Visual Observer Note], "
    "[Audio Observer Note], INTERNAL SENSOR NOTE, or quote private sensor notes verbatim. "
    "Never prefix any reply with labels such as 'Observer Note', '[Visual Observer Note]', "
    "'[Audio Observer Note]', 'internal note', or similar hidden-context markers. If a hidden "
    "note influences your reasoning, silently translate it into calm caregiver-facing advice "
    "without revealing the note, the source, or the raw observation text. If you accidentally "
    "start drafting an observer label, immediately self-correct and continue with a normal "
    "caregiver-facing sentence only. "
    "If the latest user input appears to be only silence, background noise, filler, or unintelligible fragments, "
    "do not treat it as a meaningful request. Avoid giving a full intervention response to raw placeholders such as '.', '...', '[noise]', or similar non-speech markers. "
    "Instead, remain brief and neutral, or wait for clearer caregiver input. "
    "At session start, stay quiet until the caregiver speaks or an observer note creates a "
    "clear reason to respond."
)


def _looks_like_internal_note(text: str) -> bool:
    normalized = text.strip().lower()
    markers = (
        "[visual observer note]",
        "[audio observer note]",
        "visual observer note",
        "audio observer note",
        "internal sensor note",
        "private context",
    )
    return any(marker in normalized for marker in markers)


def _sanitize_caregiver_text(text: str) -> str:
    sanitized = text.strip()
    if not sanitized:
        return ""

    patterns = (
        r"\[\s*visual observer note\s*\]",
        r"\[\s*audio observer note\s*\]",
        r"visual observer note\s*:",
        r"audio observer note\s*:",
        r"internal sensor note\s*\([^)]*\)\s*:",
        r"internal sensor note\s*:",
        r"observer note\s*:",
    )
    for pattern in patterns:
        sanitized = re.sub(pattern, "", sanitized, flags=re.IGNORECASE).strip()

    sanitized = re.sub(r"\s{2,}", " ", sanitized).strip(" :-")
    return sanitized


def _truncate_items(items: list[str], max_items: int = 14) -> list[str]:
    if len(items) <= max_items:
        return items
    return items[-max_items:]


def _build_summary_prompt(
    *,
    duration_seconds: int,
    close_reason: str,
    observer_visual_notes: list[str],
    observer_audio_notes: list[str],
    transcript_in: list[str],
    transcript_out: list[str],
) -> str:
    clipped_visual = _truncate_items(observer_visual_notes, 10)
    clipped_audio = _truncate_items(observer_audio_notes, 10)
    clipped_in = _truncate_items(transcript_in, 10)
    clipped_out = _truncate_items(transcript_out, 10)

    return (
        "You are producing a post-crisis caregiver report for an autism support session. "
        "Use concise, practical, non-diagnostic language. Use only evidence found in the "
        "provided observer notes and transcripts. Do not invent triggers or contradict the "
        "evidence. Visual Observer Notes come ONLY from the camera sensor — use them ONLY "
        "for TRIGGERS_VISUAL. Audio Observer Notes come ONLY from the microphone sensor — "
        "use them ONLY for TRIGGERS_AUDIO. NEVER attribute an audio observation as a visual "
        "trigger or vice versa. If a list is empty, state that no trigger was detected for "
        "that modality. Never quote internal note labels such as [Visual Observer Note] or "
        "[Audio Observer Note] verbatim in the output.\n\n"
        "Output MUST follow this exact structure:\n"
        "TITLE: <short title>\n"
        "TRIGGERS_VISUAL: <1 sentence based ONLY on Visual Observer Notes below>\n"
        "TRIGGERS_AUDIO: <1 sentence based ONLY on Audio Observer Notes below>\n"
        "AGENT_ACTIONS: <1-2 sentences>\n"
        "FOLLOW_UP: <1-2 sentences>\n"
        "SAFETY_NOTE: <1 sentence>\n\n"
        f"Session metadata:\n- Duration seconds: {duration_seconds}\n- Close reason: {close_reason}\n\n"
        f"Visual Observer Notes (camera/movement detection only):\n{json.dumps(clipped_visual, ensure_ascii=True)}\n\n"
        f"Audio Observer Notes (microphone/vocal detection only):\n{json.dumps(clipped_audio, ensure_ascii=True)}\n\n"
        f"Caregiver/user transcript excerpts:\n{json.dumps(clipped_in, ensure_ascii=True)}\n\n"
        f"Agent transcript excerpts:\n{json.dumps(clipped_out, ensure_ascii=True)}\n"
    )


def generate_session_summary(
    *,
    model: str,
    duration_seconds: int,
    close_reason: str,
    observer_visual_notes: list[str],
    observer_audio_notes: list[str],
    transcript_in: list[str],
    transcript_out: list[str],
) -> str:
    prompt = _build_summary_prompt(
        duration_seconds=duration_seconds,
        close_reason=close_reason,
        observer_visual_notes=observer_visual_notes,
        observer_audio_notes=observer_audio_notes,
        transcript_in=transcript_in,
        transcript_out=transcript_out,
    )
    client = genai.Client()
    response = client.models.generate_content(model=model, contents=prompt)

    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()

    return "TITLE: Session Summary\nTRIGGERS_VISUAL: No strong visual trigger detected.\nTRIGGERS_AUDIO: No strong audio trigger detected.\nAGENT_ACTIONS: The agent provided calming, practical support in real time.\nFOLLOW_UP: Keep environment low-stimulation and monitor signs of overload.\nSAFETY_NOTE: This summary is non-diagnostic and for caregiver support only."


def _extract_structured_summary(summary_text: str) -> dict[str, str]:
    fields = {
        "TITLE": "Session Summary",
        "TRIGGERS_VISUAL": "No strong visual trigger detected.",
        "TRIGGERS_AUDIO": "No strong audio trigger detected.",
        "AGENT_ACTIONS": "The agent provided calming support in real time.",
        "FOLLOW_UP": "Keep the environment low-stimulation and monitor overload signs.",
        "SAFETY_NOTE": "Non-diagnostic support summary for caregivers only.",
    }

    for line in summary_text.splitlines():
        raw = line.strip()
        if not raw or ":" not in raw:
            continue
        key, value = raw.split(":", 1)
        key = key.strip().upper()
        value = value.strip()
        if key in fields and value:
            fields[key] = value

    return fields


def _escape_markdown_v2(text: str) -> str:
    special_chars = r"_*[]()~`>#+-=|{}.!"
    escaped = []
    for ch in text:
        if ch in special_chars:
            escaped.append("\\" + ch)
        else:
            escaped.append(ch)
    return "".join(escaped)


async def _store_session_summary(record: dict[str, object]) -> None:
    await session_store.store(record)


async def _store_session_events(records: list[dict[str, object]]) -> None:
    await session_store.store_events(records)


async def _get_latest_session_summary(
    *,
    user_id: str | None = None,
    profile_id: str | None = None,
) -> dict[str, object] | None:
    return await session_store.get_latest(user_id=user_id, profile_id=profile_id)


async def _load_profile_memory_context(
    *,
    user_id: str,
    profile_id: str,
    item_limit: int,
    session_limit: int,
) -> str:
    profile = await profile_store.get_profile(profile_id, user_id=user_id)
    memory_items = await profile_store.list_profile_memory(
        profile_id,
        item_limit,
        user_id=user_id,
    )
    recent_sessions = [
        item
        for item in await session_store.list_recent(
            max(session_limit * 3, 10),
            user_id=user_id,
            profile_id=profile_id,
        )
    ][:session_limit]

    return build_private_memory_context(
        profile=profile,
        profile_memory_items=memory_items,
        recent_sessions=recent_sessions,
    )


_startup_settings = get_settings()
session_store = SessionStore(
    firestore_enabled=_startup_settings.firestore_enabled,
    firestore_collection=_startup_settings.firestore_collection,
    firestore_event_collection=_startup_settings.firestore_event_collection,
    firestore_project=_startup_settings.firestore_project,
    max_memory_items=LATEST_SESSION_MAX_ITEMS,
)
profile_store = ProfileStore(
    firestore_enabled=_startup_settings.firestore_enabled,
    profile_collection=_startup_settings.firestore_profile_collection,
    profile_memory_collection=_startup_settings.firestore_profile_memory_collection,
    firestore_project=_startup_settings.firestore_project,
)


def _format_telegram_message(*, duration_seconds: int, summary_text: str) -> str:
    minutes = max(1, round(duration_seconds / 60))
    fields = _extract_structured_summary(summary_text)

    title = _escape_markdown_v2(fields["TITLE"])
    visual = _escape_markdown_v2(fields["TRIGGERS_VISUAL"])
    audio = _escape_markdown_v2(fields["TRIGGERS_AUDIO"])
    actions = _escape_markdown_v2(fields["AGENT_ACTIONS"])
    follow_up = _escape_markdown_v2(fields["FOLLOW_UP"])
    safety = _escape_markdown_v2(fields["SAFETY_NOTE"])

    return (
        "🚨 *NeuroDecode Alert*\n"
        f"*Sesi intervensi selesai* \\(durasi: {minutes} menit\\)\n"
        f"*Ringkasan:* {title}\n\n"
        f"👁️ *Pemicu Visual:* {visual}\n"
        f"👂 *Pemicu Audio:* {audio}\n"
        f"🤖 *Tindakan Agen:* {actions}\n"
        f"💡 *Saran Tindak Lanjut:* {follow_up}\n"
        f"⚠️ *Catatan Keselamatan:* {safety}"
    )


def send_telegram_summary(*, bot_token: str, chat_id: str, text: str) -> None:
    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "MarkdownV2",
        "disable_web_page_preview": True,
    }
    encoded = urlparse.urlencode(payload).encode("utf-8")
    req = urlrequest.Request(api_url, data=encoded, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urlrequest.urlopen(req, timeout=10) as resp:
        if resp.status >= 300:
            raise RuntimeError(f"Telegram send failed with status {resp.status}")


@app.get("/health")
@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/sessions/latest")
async def sessions_latest(
    user_id: str | None = None,
    profile_id: str | None = None,
) -> dict[str, object]:
    latest = await _get_latest_session_summary(user_id=user_id, profile_id=profile_id)
    if latest is None:
        return {"status": "empty", "message": "No completed session summary yet"}
    return {"status": "ok", "session": latest}


@app.get("/sessions")
async def sessions_list(
    user_id: str | None = None,
    profile_id: str | None = None,
) -> dict[str, object]:
    items = await session_store.list_recent(
        LATEST_SESSION_MAX_ITEMS,
        user_id=user_id,
        profile_id=profile_id,
    )
    return {
        "status": "ok",
        "count": len(items),
        "sessions": items,
    }


@app.get("/profiles/{profile_id}")
async def profile_get(profile_id: str, user_id: str | None = None) -> dict[str, object]:
    profile = await profile_store.get_profile(profile_id, user_id=user_id)
    if profile is None:
        return {
            "status": "empty",
            "message": "Profile not found",
            "profile_id": profile_id,
        }
    return {"status": "ok", "profile": profile}


@app.put("/profiles/{profile_id}")
async def profile_upsert(
    profile_id: str,
    payload: dict[str, object],
    user_id: str | None = None,
) -> dict[str, object]:
    record = dict(payload)
    record["profile_id"] = profile_id
    if user_id:
        record["user_id"] = user_id
    record["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    await profile_store.upsert_profile(profile_id, record, user_id=user_id)
    return {"status": "ok", "profile": record}


@app.get("/profiles/{profile_id}/memory")
async def profile_memory_list(
    profile_id: str,
    limit: int = 10,
    user_id: str | None = None,
) -> dict[str, object]:
    safe_limit = max(1, min(limit, 50))
    items = await profile_store.list_profile_memory(
        profile_id,
        safe_limit,
        user_id=user_id,
    )
    return {
        "status": "ok",
        "profile_id": profile_id,
        "count": len(items),
        "items": items,
    }


@app.post("/profiles/{profile_id}/memory")
async def profile_memory_add(
    profile_id: str,
    payload: dict[str, object],
    user_id: str | None = None,
) -> dict[str, object]:
    record = dict(payload)
    record["profile_id"] = profile_id
    if user_id:
        record["user_id"] = user_id
    record.setdefault("active", True)
    record.setdefault("confidence", "medium")
    record["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    await profile_store.add_profile_memory(profile_id, record, user_id=user_id)
    return {"status": "ok", "item": record}


@app.get("/profiles/{profile_id}/memory-context")
async def profile_memory_context(
    profile_id: str,
    user_id: str | None = None,
) -> dict[str, object]:
    profile = await profile_store.get_profile(profile_id, user_id=user_id)
    items = await profile_store.list_profile_memory(profile_id, 5, user_id=user_id)
    sessions = await session_store.list_recent(5, user_id=user_id, profile_id=profile_id)
    context = build_private_memory_context(
        profile=profile,
        profile_memory_items=items,
        recent_sessions=sessions,
    )
    return {
        "status": "ok",
        "profile_id": profile_id,
        "profile_found": profile is not None,
        "memory_item_count": len(items),
        "recent_session_count": len(sessions),
        "context": context,
    }


@app.websocket("/ws/live")
async def ws_live(websocket: WebSocket) -> None:
    await websocket.accept()
    settings = get_settings()
    user_id = (websocket.query_params.get("user_id") or "").strip() or None
    profile_id = (websocket.query_params.get("profile_id") or "").strip() or None
    effective_system_instruction = SYSTEM_INSTRUCTION

    if settings.enable_profile_memory_context and user_id and profile_id:
        try:
            memory_context = await _load_profile_memory_context(
                user_id=user_id,
                profile_id=profile_id,
                item_limit=settings.profile_memory_item_limit,
                session_limit=settings.profile_memory_session_limit,
            )
            if memory_context:
                effective_system_instruction = (
                    f"{SYSTEM_INSTRUCTION}\n\n{memory_context}"
                )
        except Exception as e:
            print(f"[profile_memory] Failed to prepare memory context: {e}")

    if not settings.gemini_api_key:
        await websocket.send_text(
            json.dumps(
                {
                    "type": "error",
                    "message": "GEMINI_API_KEY is required. Mock mode has been removed.",
                }
            )
        )
        await websocket.close(code=1011, reason="Missing GEMINI_API_KEY")
        return

    async with GeminiLiveSession(
        model=settings.live_model,
        response_modality=settings.response_modality,
        system_instruction=effective_system_instruction,
        voice_name=settings.voice_name,
        enable_input_transcription=settings.enable_input_transcription,
        enable_output_transcription=settings.enable_output_transcription,
    ) as session:
        session_id = uuid4().hex
        session_start = time.monotonic()
        close_reason = "unknown"
        last_activity = time.monotonic()
        last_audio_note_ts = 0.0
        last_vision_note_ts = 0.0
        audio_observer_buffer = bytearray()
        observer_visual_log: list[str] = []
        observer_audio_log: list[str] = []
        transcript_in_log: list[str] = []
        transcript_out_log: list[str] = []
        session_events: list[dict[str, object]] = []
        audio_observer_task: asyncio.Task[None] | None = None
        vision_observer_task: asyncio.Task[None] | None = None
        last_vision_note_text = ""
        audio_turn_open = False
        awaiting_model_response = False
        model_turn_active = False
        print("[ws_live] Session started — Gemini connected")

        def queue_session_event(
            event_type: str,
            *,
            source: str,
            text: str | None = None,
            metadata: dict[str, object] | None = None,
        ) -> None:
            event: dict[str, object] = {
                "session_id": session_id,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "event_type": event_type,
                "source": source,
            }
            if user_id:
                event["user_id"] = user_id
            if profile_id:
                event["profile_id"] = profile_id
            if text:
                event["text"] = text
            if metadata:
                event["metadata"] = dict(metadata)
            session_events.append(event)

        queue_session_event(
            "session_started",
            source="system",
            metadata={
                "response_modality": settings.response_modality,
                "live_model": settings.live_model,
                "user_id": user_id,
                "profile_id": profile_id,
                "profile_memory_enabled": settings.enable_profile_memory_context,
            },
        )

        if settings.enable_profile_memory_context and user_id and profile_id and effective_system_instruction != SYSTEM_INSTRUCTION:
            queue_session_event(
                "profile_memory_context_loaded",
                source="profile_memory",
                metadata={
                    "user_id": user_id,
                    "profile_id": profile_id,
                    "memory_item_limit": settings.profile_memory_item_limit,
                    "session_limit": settings.profile_memory_session_limit,
                },
            )

        def can_forward_visual_context() -> bool:
            return not audio_turn_open and not awaiting_model_response and not model_turn_active

        async def run_audio_observer(observer_audio: bytes) -> None:
            try:
                note = await asyncio.to_thread(ai_engine.process_audio_chunk, observer_audio, 16000)
                if note:
                    print(f"[observer] Audio note triggered")
                    observer_audio_log.append(note)
                    queue_session_event("observer_audio_trigger", source="audio_observer", text=note)
                    await websocket.send_text(json.dumps({"type": "observer_note", "text": note}))
                    # Do not force a model response mid push-to-talk; keep this as
                    # non-turn-completing context during an active audio turn.
                    await session.send_observer_note(note, end_of_turn=False)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"[observer] Audio observer error: {e}")

        async def run_vision_observer(frame_b64: str) -> None:
            nonlocal last_vision_note_text
            try:
                note = await asyncio.to_thread(ai_engine.process_vision_frame, frame_b64)
                if note:
                    normalized_note = note.strip().lower()
                    if normalized_note and normalized_note == last_vision_note_text:
                        return
                    last_vision_note_text = normalized_note
                    print(f"[observer] Visual note triggered")
                    observer_visual_log.append(note)
                    queue_session_event("observer_visual_trigger", source="visual_observer", text=note)
                    await websocket.send_text(json.dumps({"type": "observer_note", "text": note}))
                    # Keep observer notes as passive context. This avoids repeated,
                    # unsolicited model responses when observer mode is enabled.
                    await session.send_observer_note(note, end_of_turn=False)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"[observer] Vision observer error: {e}")

        async def maybe_summarize_and_notify() -> None:
            if not settings.summary_enabled:
                return

            if not (observer_visual_log or observer_audio_log or transcript_in_log or transcript_out_log):
                return

            duration_seconds = int(max(1, time.monotonic() - session_start))

            try:
                print(f"[session_summary] Generating: visual={len(observer_visual_log)} audio={len(observer_audio_log)} in={len(transcript_in_log)} out={len(transcript_out_log)}")
                summary = await asyncio.to_thread(
                    generate_session_summary,
                    model=settings.summary_model,
                    duration_seconds=duration_seconds,
                    close_reason=close_reason,
                    observer_visual_notes=list(observer_visual_log),
                    observer_audio_notes=list(observer_audio_log),
                    transcript_in=list(transcript_in_log),
                    transcript_out=list(transcript_out_log),
                )
            except Exception as e:
                print(f"[session_summary] Failed to generate summary: {e}")
                return

            print("[session_summary] Generated post-crisis summary")

            structured = _extract_structured_summary(summary)
            duration_minutes = max(1, round(duration_seconds / 60))
            await _store_session_summary(
                {
                    "session_id": session_id,
                    "user_id": user_id,
                    "profile_id": profile_id,
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "duration_seconds": duration_seconds,
                    "duration_minutes": duration_minutes,
                    "close_reason": close_reason,
                    "summary_text": summary,
                    "stats": {
                        "audio_trigger_count": len(observer_audio_log),
                        "visual_trigger_count": len(observer_visual_log),
                        "transcript_in_count": len(transcript_in_log),
                        "transcript_out_count": len(transcript_out_log),
                    },
                    "structured": {
                        "title": structured["TITLE"],
                        "triggers_visual": structured["TRIGGERS_VISUAL"],
                        "triggers_audio": structured["TRIGGERS_AUDIO"],
                        "agent_actions": structured["AGENT_ACTIONS"],
                        "follow_up": structured["FOLLOW_UP"],
                        "safety_note": structured["SAFETY_NOTE"],
                    },
                }
            )

            if settings.telegram_bot_token and settings.telegram_chat_id:
                message = _format_telegram_message(
                    duration_seconds=duration_seconds,
                    summary_text=summary,
                )
                try:
                    await asyncio.to_thread(
                        send_telegram_summary,
                        bot_token=settings.telegram_bot_token,
                        chat_id=settings.telegram_chat_id,
                        text=message,
                    )
                    print("[telegram] Summary notification sent")
                except (urlerror.URLError, RuntimeError) as e:
                    print(f"[telegram] Failed to send summary: {e}")

            queue_session_event(
                "summary_generated",
                source="summary_engine",
                metadata={
                    "close_reason": close_reason,
                    "duration_seconds": duration_seconds,
                },
            )

        async def idle_monitor() -> None:
            """Close the WebSocket if no client activity for IDLE_TIMEOUT_SECONDS."""
            nonlocal close_reason, last_activity
            while True:
                await asyncio.sleep(5)
                idle_secs = time.monotonic() - last_activity
                if idle_secs > IDLE_TIMEOUT_SECONDS:
                    print(f"[idle_monitor] No activity for {IDLE_TIMEOUT_SECONDS}s — closing session")
                    close_reason = "idle_timeout"
                    await websocket.send_text(
                        json.dumps({"type": "error", "message": "Session closed: idle timeout"})
                    )
                    await websocket.close(code=1000, reason="Idle timeout")
                    return

        async def pump_client_to_gemini() -> None:
            nonlocal close_reason, last_activity, last_audio_note_ts, last_vision_note_ts, audio_observer_task, vision_observer_task, audio_turn_open, awaiting_model_response
            audio_chunk_count = 0
            total_audio_bytes = 0
            while True:
                raw = await websocket.receive_text()
                last_activity = time.monotonic()
                msg = json.loads(raw)
                msg_type = ensure_type(msg)
                if msg_type != "audio":
                    print(f"[client\u2192gemini] {msg_type}")

                if msg_type == "audio":
                    data_b64 = msg.get("data_b64")
                    mime_type = msg.get("mime_type") or "audio/pcm;rate=16000"
                    if not isinstance(data_b64, str):
                        raise ValueError("audio.data_b64 must be a string")
                    audio_bytes = b64_decode(data_b64)
                    audio_turn_open = True
                    awaiting_model_response = False
                    audio_chunk_count += 1
                    total_audio_bytes += len(audio_bytes)
                    await session.send_audio(audio_bytes, mime_type)

                    # Best-effort local audio signal observer; never blocks main flow.
                    audio_observer_buffer.extend(audio_bytes)
                    now = time.monotonic()
                    if (
                        len(audio_observer_buffer) >= MIN_AUDIO_BYTES_FOR_ANALYSIS
                        and (now - last_audio_note_ts) >= AUDIO_OBSERVER_COOLDOWN_SECONDS
                    ):
                        observer_audio = bytes(audio_observer_buffer)
                        audio_observer_buffer.clear()
                        last_audio_note_ts = now
                        if audio_observer_task is None or audio_observer_task.done():
                            audio_observer_task = asyncio.create_task(run_audio_observer(observer_audio))
                elif msg_type == "text":
                    text = msg.get("text")
                    end_of_turn = msg.get("end_of_turn", True)
                    if not isinstance(text, str):
                        raise ValueError("text.text must be a string")
                    if text.strip():
                        transcript_in_log.append(text.strip())
                        queue_session_event("client_text_message", source="client_text", text=text.strip())
                    await session.send_text(text, bool(end_of_turn))
                elif msg_type == "audio_stream_end":
                    print(f"[client\u2192gemini] audio_stream_end — total {audio_chunk_count} chunks, {total_audio_bytes} bytes sent to Gemini")
                    audio_turn_open = False
                    awaiting_model_response = True
                    queue_session_event(
                        "audio_turn_submitted",
                        source="client_audio",
                        metadata={
                            "chunk_count": audio_chunk_count,
                            "total_audio_bytes": total_audio_bytes,
                        },
                    )
                    await session.send_audio_stream_end()
                    audio_chunk_count = 0
                    total_audio_bytes = 0
                elif msg_type == "image":
                    data_b64 = msg.get("data_b64")
                    mime_type = msg.get("mime_type") or "image/jpeg"
                    if not isinstance(data_b64, str):
                        raise ValueError("image.data_b64 must be a string")

                    now = time.monotonic()
                    if (now - last_vision_note_ts) >= VISION_OBSERVER_COOLDOWN_SECONDS:
                        last_vision_note_ts = now
                        if vision_observer_task is None or vision_observer_task.done():
                            vision_observer_task = asyncio.create_task(run_vision_observer(data_b64))

                    if can_forward_visual_context():
                        image_bytes = b64_decode(data_b64)
                        await session.send_image(image_bytes, mime_type)
                elif msg_type == "observer_note":
                    text = msg.get("text")
                    if not isinstance(text, str):
                        raise ValueError("observer_note.text must be a string")
                    if text.strip():
                        if "[audio" in text.strip().lower():
                            observer_audio_log.append(text.strip())
                        else:
                            observer_visual_log.append(text.strip())
                    await session.send_observer_note(text, end_of_turn=False)
                elif msg_type == "close":
                    close_reason = "client_close"
                    return
                else:
                    raise ValueError(f"Unsupported message type: {msg_type}")

        async def pump_gemini_to_client() -> None:
            nonlocal last_activity, awaiting_model_response, model_turn_active
            print("[gemini\u2192client] pump started, waiting for Gemini responses...")
            # Aggregate small audio chunks to reduce WebSocket message frequency.
            # Gemini often sends many tiny PCM fragments per second; batching
            # them into ~80 ms blocks greatly reduces JSON + base64 overhead on
            # the mobile client and prevents UI-thread contention.
            _audio_pending = bytearray()
            _AUDIO_BATCH_MIN = 5760
            _AUDIO_BYTES_PER_SECOND = 24000 * 2
            _AUDIO_TARGET_LEAD_SECONDS = 0.24
            _audio_batch_count = 0
            _audio_playout_deadline: float | None = None

            async def _flush_audio_pending() -> None:
                nonlocal _audio_pending, _audio_batch_count, _audio_playout_deadline
                if not _audio_pending:
                    return
                chunk = bytes(_audio_pending)
                _audio_pending = bytearray()
                _audio_batch_count += 1
                chunk_duration_seconds = len(chunk) / _AUDIO_BYTES_PER_SECOND
                now = time.monotonic()
                if _audio_playout_deadline is None or now > _audio_playout_deadline:
                    _audio_playout_deadline = now
                send_deadline = max(
                    now,
                    _audio_playout_deadline - _AUDIO_TARGET_LEAD_SECONDS,
                )
                pacing_delay = send_deadline - now
                if pacing_delay > 0:
                    await asyncio.sleep(pacing_delay)
                print(
                    f"[gemini→client] model_audio_batch #{_audio_batch_count} bytes={len(chunk)} pending=0 pacing_ms={int(max(pacing_delay, 0) * 1000)}"
                )
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "model_audio",
                            "data_b64": b64_encode(chunk),
                            "mime_type": "audio/pcm;rate=24000",
                        }
                    )
                )
                sent_at = time.monotonic()
                _audio_playout_deadline = (
                    max(_audio_playout_deadline, sent_at) + chunk_duration_seconds
                )

            # The underlying Live SDK receive stream may complete after a turn.
            # Keep the WebSocket session alive by re-entering the receive loop.
            while True:
                async for out in session.receive():
                    print(f"[gemini\u2192client] {out.type}")
                    if out.type == "model_audio" and out.data:
                        awaiting_model_response = False
                        model_turn_active = True
                        last_activity = time.monotonic()
                        _audio_pending.extend(out.data)
                        if len(_audio_pending) == len(out.data):
                            print(
                                f"[gemini→client] audio_batch_fill start bytes={len(_audio_pending)}"
                            )
                        if len(_audio_pending) >= _AUDIO_BATCH_MIN:
                            await _flush_audio_pending()
                    elif out.type in {"model_text", "transcript_in", "transcript_out"}:
                        if out.text:
                            if out.type in {"model_text", "transcript_out"} and _looks_like_internal_note(out.text):
                                continue
                            outgoing_text = out.text
                            if out.type in {"model_text", "transcript_out"}:
                                outgoing_text = _sanitize_caregiver_text(outgoing_text)
                                if not outgoing_text or _looks_like_internal_note(outgoing_text):
                                    continue
                            if out.type != "transcript_in":
                                awaiting_model_response = False
                                model_turn_active = True
                            last_activity = time.monotonic()
                            if out.type == "transcript_in":
                                transcript_in_log.append(out.text.strip())
                            elif out.type == "transcript_out":
                                transcript_out_log.append(outgoing_text.strip())
                            elif out.type == "model_text":
                                transcript_out_log.append(outgoing_text.strip())
                            await websocket.send_text(
                                json.dumps({"type": out.type, "text": outgoing_text})
                            )
                    elif out.type == "model_audio_end":
                        await _flush_audio_pending()
                        _audio_playout_deadline = None
                        awaiting_model_response = False
                        model_turn_active = False
                        last_activity = time.monotonic()
                        print("[gemini\u2192client] model_audio_end \u2014 turn complete")
                        await websocket.send_text(json.dumps({"type": "model_audio_end"}))
                    elif out.type == "interrupted":
                        _audio_pending = bytearray()  # discard on interruption
                        _audio_playout_deadline = None
                        awaiting_model_response = False
                        model_turn_active = False
                        last_activity = time.monotonic()
                        print("[gemini\u2192client] interrupted")
                        await websocket.send_text(json.dumps({"type": "interrupted"}))

                await asyncio.sleep(0.05)

        try:
            print("[ws_live] Starting pump tasks")
            client_task = asyncio.create_task(pump_client_to_gemini())
            gemini_task = asyncio.create_task(pump_gemini_to_client())
            idle_task = asyncio.create_task(idle_monitor())

            done, pending = await asyncio.wait(
                {client_task, gemini_task, idle_task},
                return_when=asyncio.FIRST_COMPLETED,
            )

            print(f"[ws_live] Task completed: done={len(done)} pending={len(pending)}")
            for task in pending:
                task.cancel()

            for task in done:
                exc = task.exception()
                if exc is None:
                    continue
                print(f"[ws_live] Task exception: {exc}")
                if isinstance(exc, WebSocketDisconnect):
                    close_reason = "client_disconnect"
                    return
                raise exc

        except WebSocketDisconnect:
            close_reason = "client_disconnect"
            print("[ws_live] Client disconnected")
            return
        except Exception as e:
            close_reason = "error"
            print(f"[ws_live] Error: {e}")
            await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))
        finally:
            for observer_task in (audio_observer_task, vision_observer_task):
                if observer_task is None or observer_task.done():
                    continue
                observer_task.cancel()
                try:
                    await observer_task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    print(f"[observer] Background task shutdown error: {e}")

            if close_reason == "unknown":
                close_reason = "completed"
            queue_session_event(
                "session_closed",
                source="system",
                metadata={
                    "close_reason": close_reason,
                    "duration_seconds": int(max(1, time.monotonic() - session_start)),
                    "audio_trigger_count": len(observer_audio_log),
                    "visual_trigger_count": len(observer_visual_log),
                    "transcript_in_count": len(transcript_in_log),
                    "transcript_out_count": len(transcript_out_log),
                },
            )
            print(f"[ws_live] Session ending: close_reason={close_reason}")
            await maybe_summarize_and_notify()
            await _store_session_events(list(session_events))
