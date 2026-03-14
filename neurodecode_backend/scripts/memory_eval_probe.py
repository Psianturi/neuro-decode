from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass

import websockets


@dataclass
class ProbeResult:
    label: str
    transcript_out: str
    transcript_in: str
    model_text: str
    latency_ms: int


@dataclass
class PromptRunSummary:
    prompt: str
    runs: int
    no_memory_latency_avg_ms: int
    with_memory_latency_avg_ms: int
    similarity_avg: float


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


def _build_http_url_from_ws(base_ws_url: str, path: str, query: dict[str, str]) -> str:
    parsed = urllib.parse.urlparse(base_ws_url)
    scheme = "https" if parsed.scheme == "wss" else "http"
    return urllib.parse.urlunparse(
        (
            scheme,
            parsed.netloc,
            path,
            "",
            urllib.parse.urlencode(query, doseq=True),
            "",
        )
    )


def _fetch_memory_context_snapshot(
    *,
    base_ws_url: str,
    user_id: str,
    profile_id: str,
) -> dict[str, object]:
    url = _build_http_url_from_ws(
        base_ws_url,
        f"/profiles/{profile_id}/memory-context",
        {"user_id": user_id},
    )
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=15) as response:
        payload = response.read().decode("utf-8")
        data = json.loads(payload)
    return {
        "profile_found": bool(data.get("profile_found")),
        "memory_item_count": int(data.get("memory_item_count") or 0),
        "recent_session_count": int(data.get("recent_session_count") or 0),
    }


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


def _load_prompts(*, prompt_args: list[str], prompt_file: str | None) -> list[str]:
    prompts: list[str] = []
    for item in prompt_args:
        value = item.strip()
        if value:
            prompts.append(value)

    if prompt_file:
        with open(prompt_file, "r", encoding="utf-8") as f:
            for line in f:
                value = line.strip()
                if value and not value.startswith("#"):
                    prompts.append(value)

    # Deduplicate while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for item in prompts:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique


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
        action="append",
        default=[],
        help=(
            "Prompt for paired comparison. Repeat --prompt to test multiple prompts. "
            "If omitted, a default prompt is used."
        ),
    )
    parser.add_argument(
        "--prompt-file",
        default=None,
        help="Optional text file with one prompt per line.",
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
    parser.add_argument(
        "--report-json",
        default=None,
        help="Optional output path for JSON report.",
    )
    args = parser.parse_args()

    prompts = _load_prompts(prompt_args=args.prompt, prompt_file=args.prompt_file)
    if not prompts:
        prompts = [
            (
                "Anak saya mulai gelisah dan menutup telinga saat suara TV keras. "
                "Mohon arahan singkat yang praktis."
            )
        ]

    context_snapshot = _fetch_memory_context_snapshot(
        base_ws_url=args.ws_url,
        user_id=args.user_id,
        profile_id=args.profile_id,
    )

    print("=== Context Snapshot ===")
    print(f"profile_found      : {context_snapshot['profile_found']}")
    print(f"memory_item_count  : {context_snapshot['memory_item_count']}")
    print(f"recent_session_count: {context_snapshot['recent_session_count']}")

    per_prompt_summaries: list[PromptRunSummary] = []
    report: dict[str, object] = {
        "ws_url": args.ws_url,
        "user_id": args.user_id,
        "profile_id": args.profile_id,
        "runs_per_prompt": args.runs,
        "context_snapshot": context_snapshot,
        "prompts": [],
    }

    for prompt_index, prompt_text in enumerate(prompts, start=1):
        baseline_latencies: list[int] = []
        memory_latencies: list[int] = []
        similarities: list[float] = []
        prompt_runs: list[dict[str, object]] = []

        print(f"\n=== Prompt #{prompt_index} ===")
        print(prompt_text)

        for i in range(1, args.runs + 1):
            no_memory_url = _build_ws_url(args.ws_url, args.user_id, None)
            with_memory_url = _build_ws_url(args.ws_url, args.user_id, args.profile_id)

            no_memory = await _run_single_probe(
                label=f"prompt-{prompt_index}-run-{i}-no-memory",
                ws_url=no_memory_url,
                prompt=prompt_text,
                timeout_seconds=args.timeout_seconds,
            )
            with_memory = await _run_single_probe(
                label=f"prompt-{prompt_index}-run-{i}-with-memory",
                ws_url=with_memory_url,
                prompt=prompt_text,
                timeout_seconds=args.timeout_seconds,
            )

            baseline_text = no_memory.transcript_out or no_memory.model_text
            memory_text = with_memory.transcript_out or with_memory.model_text
            similarity = _jaccard_similarity(baseline_text, memory_text)

            baseline_latencies.append(no_memory.latency_ms)
            memory_latencies.append(with_memory.latency_ms)
            similarities.append(similarity)
            prompt_runs.append(
                {
                    "pair": i,
                    "no_memory_latency_ms": no_memory.latency_ms,
                    "with_memory_latency_ms": with_memory.latency_ms,
                    "similarity": round(similarity, 6),
                    "no_memory_response": baseline_text,
                    "with_memory_response": memory_text,
                }
            )

            print(f"\n--- Pair #{i} ---")
            print(f"No-memory latency : {no_memory.latency_ms} ms")
            print(f"With-memory latency: {with_memory.latency_ms} ms")
            print(f"Jaccard similarity : {similarity:.3f}")
            print("No-memory response:")
            print(baseline_text or "(empty)")
            print("With-memory response:")
            print(memory_text or "(empty)")

        prompt_summary = PromptRunSummary(
            prompt=prompt_text,
            runs=args.runs,
            no_memory_latency_avg_ms=int(statistics.mean(baseline_latencies)),
            with_memory_latency_avg_ms=int(statistics.mean(memory_latencies)),
            similarity_avg=float(statistics.mean(similarities)),
        )
        per_prompt_summaries.append(prompt_summary)
        report["prompts"].append(
            {
                "prompt": prompt_text,
                "summary": {
                    "runs": prompt_summary.runs,
                    "no_memory_latency_avg_ms": prompt_summary.no_memory_latency_avg_ms,
                    "with_memory_latency_avg_ms": prompt_summary.with_memory_latency_avg_ms,
                    "similarity_avg": round(prompt_summary.similarity_avg, 6),
                },
                "pairs": prompt_runs,
            }
        )

        print("\nPrompt summary:")
        print(f"Runs: {prompt_summary.runs}")
        print(f"No-memory latency avg: {prompt_summary.no_memory_latency_avg_ms} ms")
        print(f"With-memory latency avg: {prompt_summary.with_memory_latency_avg_ms} ms")
        print(f"Response similarity avg: {prompt_summary.similarity_avg:.3f}")

    similarity_all = [item.similarity_avg for item in per_prompt_summaries]
    no_memory_all = [item.no_memory_latency_avg_ms for item in per_prompt_summaries]
    with_memory_all = [item.with_memory_latency_avg_ms for item in per_prompt_summaries]

    print("\n=== Overall Summary ===")
    print(f"Prompt count: {len(per_prompt_summaries)}")
    print(f"Runs per prompt: {args.runs}")
    print(f"No-memory latency avg (across prompts): {int(statistics.mean(no_memory_all))} ms")
    print(f"With-memory latency avg (across prompts): {int(statistics.mean(with_memory_all))} ms")
    print(f"Response similarity avg (across prompts): {statistics.mean(similarity_all):.3f}")
    print(
        "Interpretation: lower similarity with stable latency often indicates memory context"
        " influences response content."
    )

    if args.report_json:
        with open(args.report_json, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"JSON report saved: {args.report_json}")


if __name__ == "__main__":
    asyncio.run(main())
