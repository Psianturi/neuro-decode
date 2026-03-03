from __future__ import annotations

import asyncio
import json

import websockets


async def main() -> None:
    uri = "ws://127.0.0.1:8000/ws/live"
    async with websockets.connect(uri) as ws:
        await ws.send(
            json.dumps(
                {
                    "type": "text",
                    "text": "Halo, saya butuh bantuan live.",
                    "end_of_turn": True,
                }
            )
        )

        for _ in range(5):
            msg = await ws.recv()
            print(msg)

        await ws.send(json.dumps({"type": "close"}))


if __name__ == "__main__":
    asyncio.run(main())
