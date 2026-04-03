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
        def _pick_profile_field(profile: dict, *keys: str) -> object:
            """Return first non-empty value across multiple possible key names."""
            for key in keys:
                value = profile.get(key)
                if value not in (None, "", [], {}):
                    return value
            return None

        stable_fields: tuple[tuple[str, str, tuple[str, ...]], ...] = (
            # (label, primary_key, fallback_keys...)
            ("Child",                           "child_name",             ("childName",)),
            ("Caregiver",                        "caregiver_name",         ("caregiverName",)),
            ("Language preference",              "language_preference",    ()),
            ("Known audio triggers",             "known_audio_triggers",   ("trigger_tags", "triggers")),
            ("Known visual triggers",            "known_visual_triggers",  ("trigger_tags",)),
            ("Previously effective interventions","effective_interventions",("calming_tags", "calming_supports")),
            ("Previously ineffective interventions","ineffective_interventions", ()),
            ("Communication preferences",        "communication_tags",     ("communication_preferences",)),
            ("Profile notes",                    "notes",                  ("support_notes",)),
        )
        stable_lines: list[str] = []
        for label, primary_key, fallback_keys in stable_fields:
            value = _pick_profile_field(profile, primary_key, *fallback_keys)
            if value is None:
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