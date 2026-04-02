"""
CreatorAgent + PersonaRegistry

Mirrors the Creator pattern from ed-donner/autogen but uses pre-defined
persona configs instead of dynamic code generation — safe for production.

CreatorAgent receives a SessionContext and selects (or blends) the most
appropriate persona + topic angle for the current heartbeat cycle.
"""
from __future__ import annotations

import asyncio
from typing import Any

from google import genai
from google.genai import types as genai_types

from app.moltbook.agents.base import BaseAgent
from app.moltbook.agents.messages import CommunityInsight, SessionContext

# ---------------------------------------------------------------------------
# Persona Registry — pre-defined agent personas
# ---------------------------------------------------------------------------

PERSONA_REGISTRY: dict[str, dict[str, Any]] = {
    "sensory_specialist": {
        "display_name": "Sensory Specialist",
        "system_addendum": (
            "You write from the perspective of a sensory processing specialist. "
            "Your posts focus on the neuroscience and practical management of sensory "
            "sensitivities — sound, light, texture, proprioception. You use precise "
            "but accessible language. You cite OT (occupational therapy) frameworks "
            "when relevant."
        ),
        "focus_topics": [
            "sensory diets", "sensory overload", "proprioceptive input",
            "auditory processing", "tactile defensiveness", "vestibular needs",
        ],
        "tone": "precise, evidence-informed, practical",
        "submolt": "general",
    },
    "iep_advocate": {
        "display_name": "IEP Advocate",
        "system_addendum": (
            "You write from the perspective of a parent advocate who has navigated "
            "the IEP process for years. Your posts are empowering, specific, and "
            "action-oriented. You help caregivers understand their rights and how "
            "to communicate effectively with schools."
        ),
        "focus_topics": [
            "IEP meetings", "school accommodations", "FAPE rights",
            "transition planning", "504 plans", "inclusive education",
        ],
        "tone": "empowering, practical, parent-to-parent",
        "submolt": "general",
    },
    "parent_peer": {
        "display_name": "Parent Peer",
        "system_addendum": (
            "You write as a fellow caregiver — warm, honest, and relatable. "
            "Your posts acknowledge the emotional weight of caregiving without "
            "being preachy. You share hard-won practical wisdom in plain language. "
            "You are not a clinician and don't pretend to be."
        ),
        "focus_topics": [
            "caregiver burnout", "daily routines", "sibling dynamics",
            "meltdown recovery", "self-care", "community support",
        ],
        "tone": "warm, honest, peer-to-peer",
        "submolt": "general",
    },
    "researcher": {
        "display_name": "Researcher",
        "system_addendum": (
            "You write from the perspective of someone who follows autism research "
            "closely. Your posts translate recent findings into practical takeaways "
            "for caregivers. You are careful about causation vs correlation and "
            "always note when evidence is preliminary."
        ),
        "focus_topics": [
            "autism research", "neurodiversity science", "late diagnosis",
            "gender and autism", "co-occurring conditions", "intervention evidence",
        ],
        "tone": "analytical, careful, accessible",
        "submolt": "todayilearned",
    },
    "community_connector": {
        "display_name": "Community Connector",
        "system_addendum": (
            "You write to build bridges — between caregivers, between cultures, "
            "between the autism community and the broader public. Your posts often "
            "reference Southeast Asian and Indonesian context where relevant. "
            "You celebrate neurodiversity and challenge stigma directly."
        ),
        "focus_topics": [
            "autism awareness", "stigma reduction", "cultural context",
            "Indonesia autism community", "neurodiversity movement",
            "representation in media",
        ],
        "tone": "inclusive, celebratory, bridge-building",
        "submolt": "general",
    },
}

_DEFAULT_PERSONA = "parent_peer"


def _pick_persona_for_context(ctx: SessionContext, post_count: int = 0) -> str:
    """Pick persona based on session data. Rotates across all 5 personas when data is thin."""
    import time
    personas = list(PERSONA_REGISTRY.keys())
    bucket = int(time.time() // (3600 * 2))  # changes every 2h

    # Only lock to sensory_specialist when audio/visual patterns are strongly dominant.
    # If hint always contains "audio"/"visual" (normal for this app), we'd never rotate
    # without this guard — so require >60% of total patterns to be that type.
    audio_count = len(ctx.audio_trigger_patterns)
    visual_count = len(ctx.visual_trigger_patterns)
    total = audio_count + visual_count
    hint = (ctx.dominant_topic_hint or "").lower()

    if hint:
        if "school" in hint or "iep" in hint or "transition" in hint:
            return "iep_advocate"
        if "burnout" in hint or "caregiver" in hint:
            return "parent_peer"
        # sensory only when strongly dominant (>60% of patterns)
        if total > 0 and (audio_count + visual_count) / total > 0.6:
            if audio_count / total > 0.6 or visual_count / total > 0.6:
                # Still rotate 1-in-3 cycles to avoid full lock
                if bucket % 3 != 0:
                    return "sensory_specialist"

    return personas[bucket % len(personas)]


# ---------------------------------------------------------------------------
# CreatorAgent
# ---------------------------------------------------------------------------

_CREATOR_SYSTEM = (
    "You are an editorial director for an ASD caregiving educator on Moltbook. "
    "Given anonymized session patterns from real caregiving sessions, you identify "
    "the most valuable community insight to share — something that would genuinely "
    "help other caregivers if they read it today. "
    "You never reveal private data. You synthesize patterns into universal insights. "
    "Respond in JSON only."
)


class CreatorAgent(BaseAgent):
    """
    Receives SessionContext, selects a persona, and produces a CommunityInsight
    that guides what MoltbookDraftAgent will write.

    Mirrors Creator from ed-donner: decides *what* to create and *who* creates it.
    """

    def __init__(self, model: str) -> None:
        super().__init__("Creator")
        self._model = model

    async def run(self, message: SessionContext) -> CommunityInsight:
        persona_key = _pick_persona_for_context(message)
        persona = PERSONA_REGISTRY[persona_key]

        if message.has_data:
            insight = await self._derive_from_context(message, persona_key, persona)
        else:
            insight = self._fallback_insight(persona_key, persona)

        self.log(
            "Selected persona=%s topic=%s submolt=%s",
            persona_key, insight.topic, insight.suggested_submolt,
        )
        return insight

    async def _derive_from_context(
        self,
        ctx: SessionContext,
        persona_key: str,
        persona: dict,
    ) -> CommunityInsight:
        import json

        audio_summary = "; ".join(ctx.audio_trigger_patterns[:3]) or "none"
        visual_summary = "; ".join(ctx.visual_trigger_patterns[:3]) or "none"
        follow_summary = "; ".join(ctx.common_follow_ups[:3]) or "none"

        # Build topic avoidance block from recent post titles
        avoid_block = ""
        if ctx.recent_post_titles:
            titles_str = ", ".join(f'"{t}"' for t in ctx.recent_post_titles[:5])
            avoid_block = (
                f"IMPORTANT: These topics were covered in recent posts — do NOT repeat them: {titles_str}.\n"
                "Choose a genuinely different angle or topic.\n\n"
            )

        prompt = (
            f"Recent caregiving session patterns (anonymized, {ctx.session_count} sessions, "
            f"last {ctx.hours_window}h):\n"
            f"- Audio trigger patterns: {audio_summary}\n"
            f"- Visual trigger patterns: {visual_summary}\n"
            f"- Common follow-up actions: {follow_summary}\n\n"
            f"{avoid_block}"
            f"Persona writing this post: {persona['display_name']} "
            f"(focus: {', '.join(persona['focus_topics'][:3])})\n\n"
            "Identify the single most valuable community insight to share based on these patterns.\n"
            "Respond with JSON only, no markdown:\n"
            '{"topic": "...", "angle": "...", "evidence_summary": "...", "suggested_submolt": "general or todayilearned"}'
        )

        try:
            client = genai.Client()
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=self._model,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    system_instruction=_CREATOR_SYSTEM,
                    temperature=0.6,
                    max_output_tokens=256,
                ),
            )
            raw = response.text.strip()
            # Strip markdown code fences if model adds them
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            data = json.loads(raw)
            return CommunityInsight(
                topic=data.get("topic", ctx.dominant_topic_hint or "ASD caregiving"),
                angle=data.get("angle", "practical caregiver perspective"),
                evidence_summary=data.get("evidence_summary", "patterns observed in recent sessions"),
                suggested_submolt=data.get("suggested_submolt", persona["submolt"]),
                persona_key=persona_key,
            )
        except Exception as exc:
            self.warn("Gemini insight derivation failed: %s — using fallback", exc)
            return self._fallback_insight(persona_key, persona)

    def _fallback_insight(self, persona_key: str, persona: dict) -> CommunityInsight:
        import time
        # Rotate through focus topics using time bucket
        bucket = int(time.time() // (3600 * 8))
        topic = persona["focus_topics"][bucket % len(persona["focus_topics"])]
        return CommunityInsight(
            topic=topic,
            angle="practical caregiver perspective",
            evidence_summary="based on common caregiving experiences",
            suggested_submolt=persona["submolt"],
            persona_key=persona_key,
        )
