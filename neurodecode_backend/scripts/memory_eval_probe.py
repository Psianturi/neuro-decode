from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
import urllib.parse
from dataclasses import dataclass

import websockets


@dataclass
class ProbeResult:
    label: str
    transcript_out: str
    transcript_in: str
    model_text: str
    latency_ms: int


def _build_ws_url(base_ws_url: str, user_id: str, profile_id: str | None) -> str:
    parsed = urllib.parse.urlparse(base_ws_url)
    query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    query["user_id"] = user_id
    if profile_id:
        query["profile_id"] = profile_id
    else:
        query.pop("profile_id", None)
    return urllib.parse.urlunparse(
        parsed._replace(query=urllib.parse.urlencode(query, doseq=True))
    )


def _normalize_text(text: str) -> str:
    return " ".join(text.strip().lower().split())


def _token_set(text: str) -> set[str]:
    normalized = _normalize_text(text)
    if not normalized:
        return set()
    return set(normalized.split(" "))


def _jaccard_similarity(a: str, b: str) -> float:
    ta = _token_set(a)
    tb = _token_set(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta.intersection(tb)) / len(ta.union(tb))


async def _run_single_probe(
    *,
    label: str,
    ws_url: str,
    prompt: str,
    timeout_seconds: float,
) -> ProbeResult:
    start = time.perf_counter()
    transcript_out_parts: list[str] = []
    transcript_in_parts: list[str] = []
    model_text_parts: list[str] = []

    async with websockets.connect(ws_url, max_size=8 * 1024 * 1024) as ws:
        await ws.send(
            json.dumps(
                {
                    "type": "text",
                    "text": prompt,
                    "end_of_turn": True,
                }
            )
        )

        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=timeout_seconds)
            msg = json.loads(raw)
            msg_type = (msg.get("type") or "").strip()
            if msg_type == "transcript_out":
                text = str(msg.get("text") or "").strip()
                if text:
                    transcript_out_parts.append(text)
            elif msg_type == "transcript_in":
                text = str(msg.get("text") or "").strip()
                if text:
                    transcript_in_parts.append(text)
            elif msg_type == "model_text":
                text = str(msg.get("text") or msg.get("data") or "").strip()
                if text:
                    model_text_parts.append(text)
            elif msg_type == "model_audio_end":
                break
            elif msg_type == "error":
                raise RuntimeError(str(msg.get("message") or "unknown backend error"))

        await ws.send(json.dumps({"type": "close"}))

    latency_ms = int((time.perf_counter() - start) * 1000)
    return ProbeResult(
        label=label,
        transcript_out=" ".join(transcript_out_parts).strip(),
        transcript_in=" ".join(transcript_in_parts).strip(),
        model_text=" ".join(model_text_parts).strip(),
        latency_ms=latency_ms,
    )


async def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Probe memory influence by comparing live responses with and without profile memory context."
        )
    )
    parser.add_argument(
        "--ws-url",
        default="ws://127.0.0.1:8000/ws/live",
        help="Base WS URL. Example: ws://127.0.0.1:8000/ws/live",
    )
    parser.add_argument("--user-id", default="memory-probe-user")
    parser.add_argument("--profile-id", required=True)
    parser.add_argument(
        "--prompt",
        default=(
            "Anak saya mulai gelisah dan menutup telinga saat suara TV keras. "
            "Mohon arahan singkat yang praktis."
        ),
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of paired runs (no-memory vs with-memory).",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=20.0,
        help="Timeout per server message while waiting response.",
    )
    args = parser.parse_args()

    baseline_latencies: list[int] = []
    memory_latencies: list[int] = []
    similarities: list[float] = []

    for i in range(1, args.runs + 1):
        no_memory_url = _build_ws_url(args.ws_url, args.user_id, None)
        with_memory_url = _build_ws_url(args.ws_url, args.user_id, args.profile_id)

        no_memory = await _run_single_probe(
            label=f"run-{i}-no-memory",
            ws_url=no_memory_url,
            prompt=args.prompt,
            timeout_seconds=args.timeout_seconds,
        )
        with_memory = await _run_single_probe(
            label=f"run-{i}-with-memory",
            ws_url=with_memory_url,
            prompt=args.prompt,
            timeout_seconds=args.timeout_seconds,
        )

        baseline_text = no_memory.transcript_out or no_memory.model_text
        memory_text = with_memory.transcript_out or with_memory.model_text
        similarity = _jaccard_similarity(baseline_text, memory_text)

        baseline_latencies.append(no_memory.latency_ms)
        memory_latencies.append(with_memory.latency_ms)
        similarities.append(similarity)

        print(f"\n=== Pair #{i} ===")
        print(f"No-memory latency : {no_memory.latency_ms} ms")
        print(f"With-memory latency: {with_memory.latency_ms} ms")
        print(f"Jaccard similarity : {similarity:.3f}")
        print("No-memory response:")
        print(baseline_text or "(empty)")
        print("With-memory response:")
        print(memory_text or "(empty)")

    print("\n=== Summary ===")
    print(f"Runs: {args.runs}")
    print(
        "No-memory latency avg: "
        f"{int(statistics.mean(baseline_latencies))} ms"
    )
    print(
        "With-memory latency avg: "
        f"{int(statistics.mean(memory_latencies))} ms"
    )
    print(f"Response similarity avg: {statistics.mean(similarities):.3f}")
    print(
        "Interpretation: lower similarity with stable latency often indicates memory context"
        " influences response content."
    )


if __name__ == "__main__":
    asyncio.run(main())
