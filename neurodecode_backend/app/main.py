from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from google import genai

from app.ai_processor import ai_engine
from app.gemini_live import GeminiLiveSession
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
    "At session start, stay quiet until the caregiver speaks or an observer note creates a "
    "clear reason to respond."
)


def _looks_like_internal_note(text: str) -> bool:
    normalized = text.strip().lower()
    markers = (
        "[visual observer note]",
        "[audio observer note]",
        "internal sensor note",
        "private context",
    )
    return any(marker in normalized for marker in markers)


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


async def _get_latest_session_summary() -> dict[str, object] | None:
    return await session_store.get_latest()


_startup_settings = get_settings()
session_store = SessionStore(
    firestore_enabled=_startup_settings.firestore_enabled,
    firestore_collection=_startup_settings.firestore_collection,
    firestore_project=_startup_settings.firestore_project,
    max_memory_items=LATEST_SESSION_MAX_ITEMS,
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
async def sessions_latest() -> dict[str, object]:
    latest = await _get_latest_session_summary()
    if latest is None:
        return {"status": "empty", "message": "No completed session summary yet"}
    return {"status": "ok", "session": latest}


@app.get("/sessions")
async def sessions_list() -> dict[str, object]:
    items = await session_store.list_recent(LATEST_SESSION_MAX_ITEMS)
    return {
        "status": "ok",
        "count": len(items),
        "sessions": items,
    }


@app.websocket("/ws/live")
async def ws_live(websocket: WebSocket) -> None:
    await websocket.accept()
    settings = get_settings()

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
        system_instruction=SYSTEM_INSTRUCTION,
        voice_name=settings.voice_name,
        enable_input_transcription=settings.enable_input_transcription,
        enable_output_transcription=settings.enable_output_transcription,
    ) as session:
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
        audio_observer_task: asyncio.Task[None] | None = None
        vision_observer_task: asyncio.Task[None] | None = None
        print("[ws_live] Session started — Gemini connected")

        async def run_audio_observer(observer_audio: bytes) -> None:
            try:
                note = await asyncio.to_thread(ai_engine.process_audio_chunk, observer_audio, 16000)
                if note:
                    print(f"[observer] Audio note triggered")
                    observer_audio_log.append(note)
                    await websocket.send_text(json.dumps({"type": "observer_note", "text": note}))
                    # Do not force a model response mid push-to-talk; keep this as
                    # non-turn-completing context during an active audio turn.
                    await session.send_observer_note(note, end_of_turn=False)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"[observer] Audio observer error: {e}")

        async def run_vision_observer(frame_b64: str) -> None:
            try:
                note = await asyncio.to_thread(ai_engine.process_vision_frame, frame_b64)
                if note:
                    print(f"[observer] Visual note triggered")
                    observer_visual_log.append(note)
                    await websocket.send_text(json.dumps({"type": "observer_note", "text": note}))
                    # Vision notes can arrive when the caregiver is silent; trigger
                    # an immediate model response so the UI shows guidance.
                    await session.send_observer_note(note, end_of_turn=True)
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
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "duration_seconds": duration_seconds,
                    "duration_minutes": duration_minutes,
                    "close_reason": close_reason,
                    "summary_text": summary,
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
            nonlocal close_reason, last_activity, last_audio_note_ts, last_vision_note_ts, audio_observer_task, vision_observer_task
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
                    await session.send_text(text, bool(end_of_turn))
                elif msg_type == "audio_stream_end":
                    print(f"[client\u2192gemini] audio_stream_end — total {audio_chunk_count} chunks, {total_audio_bytes} bytes sent to Gemini")
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
            nonlocal last_activity
            print("[gemini\u2192client] pump started, waiting for Gemini responses...")
            # The underlying Live SDK receive stream may complete after a turn.
            # Keep the WebSocket session alive by re-entering the receive loop.
            while True:
                async for out in session.receive():
                    print(f"[gemini\u2192client] {out.type}")
                    if out.type == "model_audio" and out.data:
                        last_activity = time.monotonic()
                        await websocket.send_text(
                            json.dumps(
                                {
                                    "type": "model_audio",
                                    "data_b64": b64_encode(out.data),
                                    "mime_type": out.mime_type or "audio/pcm;rate=24000",
                                }
                            )
                        )
                    elif out.type in {"model_text", "transcript_in", "transcript_out"}:
                        if out.text:
                            if out.type in {"model_text", "transcript_out"} and _looks_like_internal_note(out.text):
                                continue
                            last_activity = time.monotonic()
                            if out.type == "transcript_in":
                                transcript_in_log.append(out.text.strip())
                            elif out.type == "transcript_out":
                                transcript_out_log.append(out.text.strip())
                            elif out.type == "model_text":
                                transcript_out_log.append(out.text.strip())
                            await websocket.send_text(
                                json.dumps({"type": out.type, "text": out.text})
                            )
                    elif out.type == "model_audio_end":
                        last_activity = time.monotonic()
                        print("[gemini\u2192client] model_audio_end \u2014 turn complete")
                        await websocket.send_text(json.dumps({"type": "model_audio_end"}))
                    elif out.type == "interrupted":
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
            print(f"[ws_live] Session ending: close_reason={close_reason}")
            await maybe_summarize_and_notify()
