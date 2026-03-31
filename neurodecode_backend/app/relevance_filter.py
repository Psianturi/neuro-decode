"""
RelevanceFilterAgent

Filters community insights from Firestore community_insights/ before injecting
them into the Gemini Live system prompt for a caregiver session.

Rules:
- Skip insights that contradict known profile facts
  (e.g., insight suggests weighted blanket, profile says no physical pressure)
- Keep only insights relevant to main session/profile topic
- Return at most MAX_INSIGHTS_TO_INJECT insights
- If profile is None or empty, skip all insights (no basis for contradiction check)
- All filtering is done in a single Gemini call (temperature=0.0, cheap)

Privacy: community insights contain no user PII — safe to inject.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

MAX_INSIGHTS_TO_INJECT = 3
_INSIGHTS_FETCH_LIMIT = 20  # fetch more, filter down to MAX_INSIGHTS_TO_INJECT


def _build_profile_summary(profile: dict[str, Any]) -> str:
    """Compact profile summary for the filter prompt."""
    parts: list[str] = []
    child_name = (profile.get("child_name") or "").strip()
    if child_name:
        parts.append(f"Child: {child_name}")
    audio_triggers = (profile.get("known_audio_triggers") or "").strip()
    if audio_triggers:
        parts.append(f"Known audio triggers: {audio_triggers}")
    visual_triggers = (profile.get("known_visual_triggers") or "").strip()
    if visual_triggers:
        parts.append(f"Known visual triggers: {visual_triggers}")
    effective = (profile.get("effective_interventions") or "").strip()
    if effective:
        parts.append(f"Effective interventions: {effective}")
    ineffective = (profile.get("ineffective_interventions") or "").strip()
    if ineffective:
        parts.append(f"Ineffective/avoid: {ineffective}")
    notes = (profile.get("notes") or "").strip()
    if notes:
        parts.append(f"Notes: {notes[:200]}")
    return "\n".join(parts)


async def filter_community_insights(
    *,
    insights: list[dict[str, Any]],
    profile: dict[str, Any] | None,
    model: str,
) -> list[dict[str, Any]]:
    """
    Return a filtered subset of insights safe and relevant for this profile.

    Returns empty list if:
    - insights is empty
    - profile is None or has no useful fields (no basis for contradiction check)
    """
    if not insights:
        return []

    # Require at least some profile data — without it we can't check contradictions
    if not profile:
        logger.debug("[RelevanceFilter] No profile — skipping community insights")
        return []

    profile_summary = _build_profile_summary(profile)
    if not profile_summary.strip():
        logger.debug("[RelevanceFilter] Profile has no usable fields — skipping insights")
        return []

    # Build numbered insight list for the prompt
    insight_lines: list[str] = []
    for idx, item in enumerate(insights[:_INSIGHTS_FETCH_LIMIT], start=1):
        text = str(item.get("insight_text") or "").strip()
        itype = str(item.get("insight_type") or "tip").strip()
        if text:
            insight_lines.append(f"{idx}. [{itype}] {text}")

    if not insight_lines:
        return []

    prompt = (
        "You are a filter agent for an ASD caregiver support system.\n\n"
        "CHILD PROFILE:\n"
        f"{profile_summary}\n\n"
        "COMMUNITY INSIGHTS (from peer caregivers and ASD educators):\n"
        + "\n".join(insight_lines)
        + f"\n\nSelect at most {MAX_INSIGHTS_TO_INJECT} insights that:\n"
        "1. Do NOT contradict the child profile (e.g., if profile says avoid physical pressure, "
        "reject any insight suggesting weighted blankets or deep pressure)\n"
        "2. Are genuinely relevant and useful for this specific child/caregiver\n"
        "3. Add knowledge not already covered by the profile facts\n\n"
        "Respond with ONLY a JSON array of the selected insight numbers, e.g.: [1, 3, 5]\n"
        "If no insights are suitable, respond with: []"
    )

    try:
        from google import genai
        from google.genai import types as genai_types

        client = genai.Client()
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=model,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                system_instruction=None,
                temperature=0.0,
                max_output_tokens=32,
            ),
        )
        raw = (response.text or "").strip()

        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        selected_indices: list[int] = json.loads(raw)
        if not isinstance(selected_indices, list):
            return []

        result: list[dict[str, Any]] = []
        for idx in selected_indices:
            if isinstance(idx, int) and 1 <= idx <= len(insights):
                result.append(insights[idx - 1])
            if len(result) >= MAX_INSIGHTS_TO_INJECT:
                break

        logger.info(
            "[RelevanceFilter] %d/%d insights kept for injection",
            len(result), len(insights),
        )
        return result

    except Exception as exc:
        logger.warning("[RelevanceFilter] Filter call failed, skipping insights: %s", exc)
        return []
