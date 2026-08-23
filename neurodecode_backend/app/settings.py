from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str | None

    live_model: str
    response_modality: str
    voice_name: str | None

    enable_input_transcription: bool
    enable_output_transcription: bool
    enable_profile_memory_context: bool
    profile_memory_item_limit: int
    profile_memory_session_limit: int

    summary_enabled: bool
    summary_model: str
    telegram_bot_token: str | None
    telegram_chat_id: str | None

    firestore_enabled: bool
    firestore_collection: str
    firestore_event_collection: str
    firestore_profile_collection: str
    firestore_profile_memory_collection: str
    firestore_notification_collection: str
    firestore_project: str | None

    admin_debug_enabled: bool
    admin_debug_token: str | None
    admin_debug_max_items: int

    fcm_enabled: bool
    firestore_push_device_collection: str
    firestore_clinical_collection: str
    admin_secret: str | None
    followup_delay_hours: int
    followup_min_duration_seconds: int

    a2a_url: str | None
    a2a_skill_enrichment_enabled: bool
    a2a_api_key: str | None


def get_settings() -> Settings:
    # The Google GenAI SDK will auto-pick `GEMINI_API_KEY`/`GOOGLE_API_KEY`.
    # We still read it to validate required runtime config.
    gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    live_model = os.getenv(
        "NEURODECODE_LIVE_MODEL", "gemini-2.5-flash-native-audio-preview-12-2025"
    )
    response_modality = os.getenv("NEURODECODE_RESPONSE_MODALITY", "AUDIO").upper()
    voice_name = os.getenv("NEURODECODE_VOICE_NAME") or None

    enable_input_transcription = os.getenv(
        "NEURODECODE_INPUT_TRANSCRIPTION", "1"
    ).strip() not in {"0", "false", "False"}
    enable_output_transcription = os.getenv(
        "NEURODECODE_OUTPUT_TRANSCRIPTION", "1"
    ).strip() not in {"0", "false", "False"}
    enable_profile_memory_context = os.getenv(
        "NEURODECODE_ENABLE_PROFILE_MEMORY_CONTEXT", "0"
    ).strip() not in {"0", "false", "False"}
    profile_memory_item_limit = max(
        1,
        min(int(os.getenv("NEURODECODE_PROFILE_MEMORY_ITEM_LIMIT", "5")), 10),
    )
    profile_memory_session_limit = max(
        1,
        min(int(os.getenv("NEURODECODE_PROFILE_MEMORY_SESSION_LIMIT", "3")), 10),
    )

    summary_enabled = os.getenv("NEURODECODE_SUMMARY_ENABLED", "1").strip() not in {
        "0",
        "false",
        "False",
    }
    # Cost-efficient default for post-session summaries.
    summary_model = os.getenv("NEURODECODE_SUMMARY_MODEL", "gemini-2.5-flash-lite")
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN") or None
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID") or None

    firestore_enabled = os.getenv("NEURODECODE_FIRESTORE_ENABLED", "1").strip() not in {
        "0",
        "false",
        "False",
    }
    firestore_collection = os.getenv("NEURODECODE_FIRESTORE_COLLECTION", "sessions")
    firestore_event_collection = os.getenv(
        "NEURODECODE_FIRESTORE_EVENT_COLLECTION", "session_events"
    )
    firestore_profile_collection = os.getenv(
        "NEURODECODE_FIRESTORE_PROFILE_COLLECTION", "profiles"
    )
    firestore_profile_memory_collection = os.getenv(
        "NEURODECODE_FIRESTORE_PROFILE_MEMORY_COLLECTION", "profile_memory"
    )
    firestore_notification_collection = os.getenv(
        "NEURODECODE_FIRESTORE_NOTIFICATION_COLLECTION", "notification_items"
    )
    firestore_project = os.getenv("NEURODECODE_FIRESTORE_PROJECT") or None

    admin_debug_enabled = os.getenv(
        "NEURODECODE_ADMIN_DEBUG_ENABLED", "1"
    ).strip() not in {"0", "false", "False"}
    admin_debug_token = os.getenv("NEURODECODE_ADMIN_DEBUG_TOKEN") or None
    admin_debug_max_items = max(
        20,
        min(int(os.getenv("NEURODECODE_ADMIN_DEBUG_MAX_ITEMS", "300")), 2000),
    )

    fcm_enabled = os.getenv("NEURODECODE_FCM_ENABLED", "0").strip() not in {
        "0",
        "false",
        "False",
    }
    firestore_push_device_collection = os.getenv(
        "NEURODECODE_FIRESTORE_PUSH_DEVICE_COLLECTION", "push_device_tokens"
    )
    firestore_clinical_collection = os.getenv(
        "NEURODECODE_FIRESTORE_CLINICAL_COLLECTION", "clinical_resources"
    )
    admin_secret = os.getenv("NEURODECODE_ADMIN_SECRET") or None
    followup_delay_hours = max(
        1, min(int(os.getenv("NEURODECODE_FOLLOWUP_DELAY_HOURS", "4")), 48)
    )
    followup_min_duration_seconds = max(
        60, min(int(os.getenv("NEURODECODE_FOLLOWUP_MIN_DURATION_SECONDS", "600")), 7200)
    )

    a2a_url = os.getenv("NEURODECODE_A2A_URL", "").strip() or None
    a2a_skill_enrichment_enabled = os.getenv(
        "NEURODECODE_A2A_SKILL_ENRICHMENT", "0"
    ).strip() not in {"0", "false", "False"}
    a2a_api_key = os.getenv("NEURODECODE_A2A_API_KEY", "").strip() or None

    return Settings(
        gemini_api_key=gemini_api_key,
        live_model=live_model,
        response_modality=response_modality,
        voice_name=voice_name,
        enable_input_transcription=enable_input_transcription,
        enable_output_transcription=enable_output_transcription,
        enable_profile_memory_context=enable_profile_memory_context,
        profile_memory_item_limit=profile_memory_item_limit,
        profile_memory_session_limit=profile_memory_session_limit,
        summary_enabled=summary_enabled,
        summary_model=summary_model,
        telegram_bot_token=telegram_bot_token,
        telegram_chat_id=telegram_chat_id,
        firestore_enabled=firestore_enabled,
        firestore_collection=firestore_collection,
        firestore_event_collection=firestore_event_collection,
        firestore_profile_collection=firestore_profile_collection,
        firestore_profile_memory_collection=firestore_profile_memory_collection,
        firestore_notification_collection=firestore_notification_collection,
        firestore_project=firestore_project,
        admin_debug_enabled=admin_debug_enabled,
        admin_debug_token=admin_debug_token,
        admin_debug_max_items=admin_debug_max_items,
        fcm_enabled=fcm_enabled,
        firestore_push_device_collection=firestore_push_device_collection,
        firestore_clinical_collection=firestore_clinical_collection,
        admin_secret=admin_secret,
        followup_delay_hours=followup_delay_hours,
        followup_min_duration_seconds=followup_min_duration_seconds,
        a2a_url=a2a_url,
        a2a_skill_enrichment_enabled=a2a_skill_enrichment_enabled,
        a2a_api_key=a2a_api_key,
    )
