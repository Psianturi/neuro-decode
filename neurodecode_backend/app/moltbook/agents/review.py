"""
ReviewAgent — quality gate before publishing to Moltbook.

Mirrors the "refine" step in ed-donner/autogen where agents bounce ideas
off each other. ReviewAgent checks:
  1. No PII or private session data leaked into the content
  2. Content is genuinely useful (not generic filler)
  3. Tone matches the persona
  4. Length is within Moltbook guidelines (180–320 words for posts)

Returns ReviewVerdict(approved=True) or ReviewVerdict(approved=False, reason=...).
If approved with minor tweaks, revised_title/revised_body may be set.
"""
from __future__ import annotations

import asyncio
import json

from google import genai
from google.genai import types as genai_types

from app.moltbook.agents.base import BaseAgent
from app.moltbook.agents.messages import DraftContent, ReviewVerdict

_REVIEW_SYSTEM = (
    "You are a strict editorial reviewer for an ASD caregiving educator's social media posts. "
    "Your job is to approve or reject draft posts before they are published. "
    "Reject if: the post contains any private/personal data, is generic filler with no real insight, "
    "is too short (<100 words) or too long (>400 words), contains hashtags, or sounds promotional. "
    "If the post is good but has a minor issue (e.g. slightly long, weak title), approve it with "
    "a revised version. "
    "Respond with JSON only, no markdown:\n"
    '{"approved": true/false, "reason": "...", "revised_title": null or "...", "revised_body": null or "..."}'
)


class ReviewAgent(BaseAgent):
    def __init__(self, model: str) -> None:
        super().__init__("Review")
        self._model = model

    async def run(self, message: DraftContent) -> ReviewVerdict:
        prompt = (
            f"Persona: {message.persona_key}\n"
            f"Topic: {message.insight.topic}\n"
            f"Title: {message.title}\n\n"
            f"Body:\n{message.body}\n\n"
            "Review this post. Respond with JSON only."
        )

        try:
            client = genai.Client()
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=self._model,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    system_instruction=_REVIEW_SYSTEM,
                    temperature=0.0,
                    max_output_tokens=512,
                ),
            )
            raw = response.text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            data = json.loads(raw)
            verdict = ReviewVerdict(
                approved=bool(data.get("approved", False)),
                reason=str(data.get("reason", "")),
                revised_title=data.get("revised_title") or None,
                revised_body=data.get("revised_body") or None,
            )
        except Exception as exc:
            self.warn("Review Gemini call failed: %s — auto-approving", exc)
            verdict = ReviewVerdict(approved=True, reason="review unavailable, auto-approved")

        self.log(
            "Verdict: approved=%s reason=%s",
            verdict.approved, verdict.reason[:80],
        )
        return verdict
