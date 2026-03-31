from __future__ import annotations


def build_private_memory_context(
    *,
    profile: dict[str, object] | None,
    profile_memory_items: list[dict[str, object]],
    recent_sessions: list[dict[str, object]],
    community_insights: list[dict[str, object]] | None = None,
) -> str:
    lines: list[str] = []

    if profile:
        stable_fields = (
            ("child_name", "Child"),
            ("caregiver_name", "Caregiver"),
            ("language_preference", "Language preference"),
            ("known_audio_triggers", "Known audio triggers"),
            ("known_visual_triggers", "Known visual triggers"),
            ("effective_interventions", "Previously effective interventions"),
            ("ineffective_interventions", "Previously ineffective interventions"),
            ("notes", "Profile notes"),
        )
        stable_lines: list[str] = []
        for key, label in stable_fields:
            value = profile.get(key)
            if value in (None, "", [], {}):
                continue
            stable_lines.append(f"- {label}: {value}")
        if stable_lines:
            lines.append("Profile facts:")
            lines.extend(stable_lines)

    if profile_memory_items:
        lines.append("Curated memory:")
        for item in profile_memory_items[:5]:
            title = str(item.get("title") or "Untitled memory").strip()
            content = str(item.get("content") or "").strip()
            if not content:
                continue
            memory_type = str(item.get("memory_type") or "memory").strip()
            lines.append(f"- [{memory_type}] {title}: {content}")

    if recent_sessions:
        lines.append("Recent session patterns:")
        for item in recent_sessions[:3]:
            structured = item.get("structured") if isinstance(item.get("structured"), dict) else {}
            title = str(structured.get("title") or item.get("summary_text") or "Recent session").strip()
            visual = str(structured.get("triggers_visual") or "").strip()
            audio = str(structured.get("triggers_audio") or "").strip()
            follow_up = str(structured.get("follow_up") or "").strip()
            summary_bits = [title]
            if visual:
                summary_bits.append(f"visual={visual}")
            if audio:
                summary_bits.append(f"audio={audio}")
            if follow_up:
                summary_bits.append(f"follow_up={follow_up}")
            lines.append("- " + " | ".join(summary_bits))

    if community_insights:
        lines.append("Community insights (peer caregivers & ASD educators — non-contradictory, pre-filtered):")
        for item in community_insights:
            text = str(item.get("insight_text") or "").strip()
            itype = str(item.get("insight_type") or "tip").strip()
            if text:
                lines.append(f"- [{itype}] {text}")

    if not lines:
        return ""

    return (
        "PRIVATE MEMORY CONTEXT (DO NOT QUOTE VERBATIM TO USER):\n"
        + "\n".join(lines)
    )