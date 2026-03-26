"""
Moltbook AI Verification Challenge Solver.

Moltbook's anti-spam system wraps a simple math word-problem in heavy obfuscation:
  - Alternating uppercase/lowercase letters
  - Scattered bracket and symbol noise: [ ] ^ / - 
  - "Shattered" words (letters split by symbols)
  - Lobster-themed framing ("A lobster swims at...")

Example:
  "A] lO^bSt-Er S[wImS aT/ tW]eNn-Tyy mE^tE[rS aNd] SlO/wS bY^ fI[vE"
  → "A lobster swims at twenty meters and slows by five"
  → 20 - 5 = 15.00

Strategy:
  1. Strip all noise characters and normalize to lowercase plaintext.
  2. Send ONLY the stripped plaintext to Gemini with a tightly-scoped prompt.
     (Isolated from persona — no EDUCATOR_SYSTEM_PROMPT.)
  3. Parse the numeric answer and format as "X.XX".

This module is intentionally stateless and side-effect-free.
"""
from __future__ import annotations

import logging
import re

from google import genai
from google.genai import types as genai_types

logger = logging.getLogger(__name__)

# Characters that are noise in obfuscated challenges
_NOISE_PATTERN = re.compile(r"[\[\]^/\-\\]")

# Isolate the solver from any persona — pure math extraction
_SOLVER_SYSTEM_PROMPT = (
    "You are a precise math word-problem solver. "
    "Read the sentence and identify the two numbers and the arithmetic operation "
    "(add, subtract, multiply, divide). "
    "Respond with ONLY the numeric answer formatted to exactly 2 decimal places. "
    "Example: if the answer is 15, respond: 15.00. "
    "No explanation. No units. Just the number."
)


def _strip_obfuscation(challenge_text: str) -> str:
    """
    Remove noise characters and normalize case so Gemini sees clean text.
    Input:  "A] lO^bSt-Er S[wImS aT/ tW]eNn-Tyy mE^tE[rS aNd] SlO/wS bY^ fI[vE"
    Output: "A lobster swims at twenty meters and slows by five"
    """
    cleaned = _NOISE_PATTERN.sub("", challenge_text)
    # Collapse any double-spaces created by removal
    cleaned = re.sub(r" {2,}", " ", cleaned)
    return cleaned.lower().strip()


def _format_answer(raw: str) -> str | None:
    """
    Extract a numeric value from Gemini's response and format as "X.XX".
    Returns None if parsing fails.
    """
    raw = raw.strip()
    # Accept plain number like "15", "15.0", "15.00", "-3.5"
    match = re.search(r"-?\d+(?:\.\d+)?", raw)
    if not match:
        return None
    try:
        value = float(match.group())
        return f"{value:.2f}"
    except ValueError:
        return None


async def solve_challenge(challenge_text: str, model: str) -> str | None:
    """
    Main entry point.

    Args:
        challenge_text: Raw obfuscated string from Moltbook API.
        model: Gemini model name (use summary_model to keep costs low).

    Returns:
        Answer string formatted as "X.XX", or None if solving failed.
    """
    cleaned = _strip_obfuscation(challenge_text)
    logger.debug("Challenge (cleaned): %s", cleaned)

    prompt = f'Solve this math word problem: "{cleaned}"'

    try:
        client = genai.Client()
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                system_instruction=_SOLVER_SYSTEM_PROMPT,
                temperature=0.0,   # Deterministic — math has one correct answer
                max_output_tokens=16,
            ),
        )
        raw_answer = response.text
        answer = _format_answer(raw_answer)
        if answer is None:
            logger.warning(
                "Challenge solver: could not parse numeric answer from: %r", raw_answer
            )
        else:
            logger.info("Challenge solved: %s → %s", cleaned, answer)
        return answer
    except Exception as exc:
        logger.error("Challenge solver error: %s", exc, exc_info=True)
        return None


async def handle_verification(
    response_json: dict,
    model: str,
    moltbook_client,  # MoltbookClient — avoid circular import by using Any
) -> bool:
    """
    If response_json contains a verification challenge, solve and submit it.

    Returns True if verification succeeded or not required.
    Returns False if solving or submission failed.
    """
    if not response_json.get("verification_required"):
        # No challenge — content published immediately (trusted agent)
        return True

    # Navigate to challenge payload (structure varies by content type)
    content = (
        response_json.get("post")
        or response_json.get("comment")
        or response_json.get("submolt")
        or {}
    )
    verification = content.get("verification", {})
    verification_code = verification.get("verification_code")
    challenge_text = verification.get("challenge_text")

    if not verification_code or not challenge_text:
        logger.error("Verification challenge missing code or text: %s", response_json)
        return False

    answer = await solve_challenge(challenge_text, model)
    if answer is None:
        logger.error("Could not solve challenge: %s", challenge_text)
        return False

    try:
        result = await moltbook_client.verify(verification_code, answer)
        if result.get("success"):
            logger.info("Verification passed. Content published.")
            return True
        else:
            logger.warning("Verification failed: %s", result)
            return False
    except Exception as exc:
        logger.error("Verification submission error: %s", exc, exc_info=True)
        return False
