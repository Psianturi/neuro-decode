from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from app.gemini_live import GeminiLiveSession
from app.mock_live import MockLiveSession
from app.protocol import b64_decode, b64_encode, ensure_type
from app.settings import get_settings


load_dotenv()

app = FastAPI(title="NeuroDecode AI Backend")

IDLE_TIMEOUT_SECONDS = 45


SYSTEM_INSTRUCTION = (
    "You are NeuroDecode AI, a real-time decision-support assistant for caregivers "
    "supporting autistic children. You do NOT diagnose or provide medical advice. "
    "You provide practical, safe, calming suggestions, and you ask clarifying "
    "questions when unsure. If there is risk of harm, advise seeking professional "
    "help or emergency services. Be concise and calm."
)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.websocket("/ws/live")
async def ws_live(websocket: WebSocket) -> None:
    await websocket.accept()
    settings = get_settings()

    session_cm: Any
    if settings.gemini_api_key and not settings.force_mock:
        session_cm = GeminiLiveSession(
            model=settings.live_model,
            response_modality=settings.response_modality,
            system_instruction=SYSTEM_INSTRUCTION,
            voice_name=settings.voice_name,
            enable_input_transcription=settings.enable_input_transcription,
            enable_output_transcription=settings.enable_output_transcription,
        )
    else:
        session_cm = MockLiveSession()

    async with session_cm as session:
        last_activity = time.monotonic()

        async def idle_monitor() -> None:
            """Close the WebSocket if no client activity for IDLE_TIMEOUT_SECONDS."""
            nonlocal last_activity
            while True:
                await asyncio.sleep(5)
                if time.monotonic() - last_activity > IDLE_TIMEOUT_SECONDS:
                    print(f"[idle_monitor] No activity for {IDLE_TIMEOUT_SECONDS}s — closing session")
                    await websocket.send_text(
                        json.dumps({"type": "error", "message": "Session closed: idle timeout"})
                    )
                    await websocket.close(code=1000, reason="Idle timeout")
                    return

        async def pump_client_to_gemini() -> None:
            nonlocal last_activity
            while True:
                raw = await websocket.receive_text()
                last_activity = time.monotonic()
                msg = json.loads(raw)
                msg_type = ensure_type(msg)

                if msg_type == "audio":
                    data_b64 = msg.get("data_b64")
                    mime_type = msg.get("mime_type") or "audio/pcm;rate=16000"
                    if not isinstance(data_b64, str):
                        raise ValueError("audio.data_b64 must be a string")
                    audio_bytes = b64_decode(data_b64)
                    await session.send_audio(audio_bytes, mime_type)
                elif msg_type == "text":
                    text = msg.get("text")
                    end_of_turn = msg.get("end_of_turn", True)
                    if not isinstance(text, str):
                        raise ValueError("text.text must be a string")
                    await session.send_text(text, bool(end_of_turn))
                elif msg_type == "observer_note":
                    text = msg.get("text")
                    if not isinstance(text, str):
                        raise ValueError("observer_note.text must be a string")
                    await session.send_observer_note(text)
                elif msg_type == "close":
                    return
                else:
                    raise ValueError(f"Unsupported message type: {msg_type}")

        async def pump_gemini_to_client() -> None:
            async for out in session.receive():
                if out.type == "model_audio" and out.data:
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
                        await websocket.send_text(
                            json.dumps({"type": out.type, "text": out.text})
                        )
                elif out.type == "model_audio_end":
                    await websocket.send_text(json.dumps({"type": "model_audio_end"}))
                elif out.type == "interrupted":
                    await websocket.send_text(json.dumps({"type": "interrupted"}))

        try:
            client_task = asyncio.create_task(pump_client_to_gemini())
            gemini_task = asyncio.create_task(pump_gemini_to_client())
            idle_task = asyncio.create_task(idle_monitor())

            done, pending = await asyncio.wait(
                {client_task, gemini_task, idle_task},
                return_when=asyncio.FIRST_EXCEPTION,
            )

            for task in pending:
                task.cancel()

            for task in done:
                exc = task.exception()
                if exc is None:
                    continue
                if isinstance(exc, WebSocketDisconnect):
                    return
                raise exc

        except WebSocketDisconnect:
            return
        except Exception as e:
            await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))
