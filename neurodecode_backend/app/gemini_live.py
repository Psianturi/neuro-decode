from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, AsyncIterator

from google import genai
from google.genai import types


@dataclass
class LiveOut:
    type: str
    data: bytes | None = None
    text: str | None = None
    mime_type: str | None = None


class GeminiLiveSession:
    """Thin wrapper around google-genai Live API session.

    We intentionally keep this small and explicit so it is easy
    to bridge from a WebSocket client (Flutter) to Gemini Live.
    """

    def __init__(
        self,
        *,
        model: str,
        response_modality: str,
        system_instruction: str,
        voice_name: str | None = None,
        enable_input_transcription: bool = True,
        enable_output_transcription: bool = True,
    ) -> None:
        self._client = genai.Client()
        self._model = model
        self._response_modality = response_modality
        self._system_instruction = system_instruction
        self._voice_name = voice_name
        self._enable_input_transcription = enable_input_transcription
        self._enable_output_transcription = enable_output_transcription

        self._cm: Any | None = None
        self._session: Any | None = None

    async def __aenter__(self) -> "GeminiLiveSession":
        config: dict[str, Any] = {
            "response_modalities": [self._response_modality],
            "system_instruction": self._system_instruction,
        }

        # Disable thinking for AUDIO modality to prevent chain-of-thought
        # text from leaking through model_turn parts.
        if self._response_modality.upper() == "AUDIO":
            config["thinking_config"] = {"thinking_budget": 0}

        if self._voice_name:
            config["speech_config"] = {
                "voice_config": {"prebuilt_voice_config": {"voice_name": self._voice_name}}
            }

        if self._enable_input_transcription:
            config["input_audio_transcription"] = {}
        if self._enable_output_transcription:
            config["output_audio_transcription"] = {}

        # Keep the SDK's async context manager so we can exit it reliably.
        self._cm = self._client.aio.live.connect(
            model=self._model,
            config=config,
        )
        self._session = await self._cm.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._cm is not None:
            await self._cm.__aexit__(exc_type, exc, tb)
        self._cm = None
        self._session = None

    async def send_audio(self, audio_bytes: bytes, mime_type: str) -> None:
        if self._session is None:
            raise RuntimeError("Live session not started")

        blob = types.Blob(data=audio_bytes, mime_type=mime_type)
        await self._session.send_realtime_input(audio=blob)

    async def send_text(self, text: str, end_of_turn: bool = True) -> None:
        if self._session is None:
            raise RuntimeError("Live session not started")

        await self._session.send_client_content(
            turns={"role": "user", "parts": [{"text": text}]},
            turn_complete=end_of_turn,
        )

    async def send_image(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> None:
        """Send a camera frame to the Live session as visual context."""
        if self._session is None:
            raise RuntimeError("Live session not started")

        blob = types.Blob(data=image_bytes, mime_type=mime_type)
        await self._session.send_realtime_input(media=blob)

    async def send_observer_note(self, text: str) -> None:
        if self._session is None:
            raise RuntimeError("Live session not started")

        note = (
            "INTERNAL SENSOR NOTE (PRIVATE CONTEXT - DO NOT REPEAT VERBATIM TO USER): "
            f"{text}"
        )

        # Best-effort: realtime text tends to be less disruptive than client content.
        # If SDK signature differs, fall back to client content.
        try:
            await self._session.send_realtime_input(text=note)
        except TypeError:
            await self._session.send_client_content(
                turns={"role": "user", "parts": [{"text": note}]},
                turn_complete=False,
            )

    async def receive(self) -> AsyncIterator[LiveOut]:
        if self._session is None:
            raise RuntimeError("Live session not started")

        async for msg in self._session.receive():
            # Audio chunks (SDK convenience field)
            data = getattr(msg, "data", None)
            if isinstance(data, (bytes, bytearray)) and data:
                yield LiveOut(
                    type="model_audio",
                    data=bytes(data),
                    mime_type="audio/pcm;rate=24000",
                )

            server_content = getattr(msg, "server_content", None)
            if server_content:
                if getattr(server_content, "interrupted", False) is True:
                    yield LiveOut(type="interrupted")

                input_tx = getattr(server_content, "input_transcription", None)
                if input_tx and getattr(input_tx, "text", None):
                    yield LiveOut(type="transcript_in", text=input_tx.text)

                output_tx = getattr(server_content, "output_transcription", None)
                if output_tx and getattr(output_tx, "text", None):
                    yield LiveOut(type="transcript_out", text=output_tx.text)

                if getattr(server_content, "turn_complete", False) is True:
                    yield LiveOut(type="model_audio_end")

                model_turn = getattr(server_content, "model_turn", None)
                if model_turn and getattr(model_turn, "parts", None):
                    # In AUDIO modality the model_turn text is internal
                    # chain-of-thought / thinking — never forward it. Only yield model_text when response modality is TEXT.
                    if self._response_modality.upper() != "AUDIO":
                        for part in model_turn.parts:
                            text = getattr(part, "text", None)
                            if isinstance(text, str) and text.strip():
                                yield LiveOut(type="model_text", text=text)

            await asyncio.sleep(0)
