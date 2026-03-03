from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import AsyncIterator


@dataclass
class MockMessage:
    type: str
    data: bytes | None = None
    text: str | None = None
    interrupted: bool = False


class MockLiveSession:
    """A tiny fake Gemini Live session.

    Useful to validate the WebSocket plumbing without credentials.
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[MockMessage] = asyncio.Queue()
        self._closed = False

    async def __aenter__(self) -> "MockLiveSession":
        await self._queue.put(
            MockMessage(type="transcript_out", text="[mock] Live session started")
        )
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self._closed = True

    async def send_audio(self, audio_bytes: bytes, mime_type: str) -> None:
        # Pretend to "hear" something.
        await self._queue.put(MockMessage(type="transcript_in", text="[mock] audio"))

    async def send_text(self, text: str, end_of_turn: bool = True) -> None:
        await self._queue.put(MockMessage(type="transcript_in", text=text))
        if end_of_turn:
            await self._queue.put(
                MockMessage(type="transcript_out", text=f"[mock] You said: {text}")
            )

    async def send_observer_note(self, text: str) -> None:
        await self._queue.put(
            MockMessage(type="transcript_out", text=f"[mock][observer] {text}")
        )

    async def receive(self) -> AsyncIterator[MockMessage]:
        while not self._closed:
            msg = await self._queue.get()
            yield msg
