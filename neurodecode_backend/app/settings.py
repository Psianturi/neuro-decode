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

    summary_enabled: bool
    summary_model: str
    telegram_bot_token: str | None
    telegram_chat_id: str | None


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

    summary_enabled = os.getenv("NEURODECODE_SUMMARY_ENABLED", "1").strip() not in {
        "0",
        "false",
        "False",
    }
    summary_model = os.getenv("NEURODECODE_SUMMARY_MODEL", "gemini-2.0-flash")
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN") or None
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID") or None

    return Settings(
        gemini_api_key=gemini_api_key,
        live_model=live_model,
        response_modality=response_modality,
        voice_name=voice_name,
        enable_input_transcription=enable_input_transcription,
        enable_output_transcription=enable_output_transcription,
        summary_enabled=summary_enabled,
        summary_model=summary_model,
        telegram_bot_token=telegram_bot_token,
        telegram_chat_id=telegram_chat_id,
    )
