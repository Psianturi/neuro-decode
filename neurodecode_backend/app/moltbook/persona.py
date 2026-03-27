"""
NeuroBuddy Educator persona for Moltbook.

Generates:
  - Original educational posts about ASD caregiving
  - Contextual replies to comments on NeuroBuddy's posts
  - Thoughtful comments on other agents' relevant posts

Uses plain Gemini text (NOT Gemini Live / audio).
PRIVATE MEMORY CONTEXT is never injected here.
"""
from __future__ import annotations

import logging
from typing import Literal

from google import genai
from google.genai import types as genai_types

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Persona system prompt
# ---------------------------------------------------------------------------

EDUCATOR_SYSTEM_PROMPT = """\
You are NeuroBuddy, a warm and knowledgeable ASD (Autism Spectrum Disorder) \
caregiving educator on a social platform called Moltbook — a community of AI agents.

Your mission is to share practical, empathetic, and evidence-informed knowledge \
about supporting autistic individuals and their caregivers.

RULES:
- Always maintain a supportive, non-judgmental, and hopeful tone.
- Write in English.
- Never diagnose, prescribe, or replace professional medical advice.
- Never reference private user data, sensor readings, or real children.
- Never fabricate statistics or cite specific studies unless you are certain.
- Posts should be 150–350 words. Comments/replies 60–150 words.
- Avoid hashtags, emojis overuse, and marketing language.
- Do not mention NeuroDecode the app & repository project unless directly asked.
- Be a community member — engage genuinely, not as a broadcast channel.
"""

# Topics the Educator rotates through
EDUCATOR_TOPICS = [
    "sensory overload signs and immediate calming strategies",
    "communication tips for caregivers during meltdown moments",
    "building predictable routines for children with ASD",
    "understanding the difference between a meltdown and a tantrum",
    "how to explain ASD to siblings and extended family",
    "self-care practices for ASD caregivers to prevent burnout",
    "visual schedules and how to create them at home",
    "the role of special interests in ASD therapy and bonding",
    "transitioning strategies between activities for autistic children",
    "how sensory diets work and when to consider them",
    "positive behavior support: strengths-based language",
    "navigating school IEP meetings: practical tips for caregivers",
    "sleep challenges in autism and evidence-based approaches",
    "using breathing exercises with young autistic children",
    "the AAC (augmentative communication) basics for caregivers",
]


def _pick_topic(post_count: int) -> str:
    return EDUCATOR_TOPICS[post_count % len(EDUCATOR_TOPICS)]


# ---------------------------------------------------------------------------
# Gemini text client (lazy, module-level)
# ---------------------------------------------------------------------------

_gemini_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = genai.Client()
    return _gemini_client


def _text_model(settings_model: str) -> str:
    # Use the summary model (gemini-2.5-flash-lite) to keep costs low.
    return settings_model


# ---------------------------------------------------------------------------
# Content generators
# ---------------------------------------------------------------------------


async def generate_post(topic: str, model: str) -> tuple[str, str]:
    """
    Returns (title, body) for a new educational post on Moltbook.
    """
    prompt = (
        f"Write an educational post for ASD caregivers about: {topic}.\n"
        "Format: first line = post TITLE (max 120 characters, no quotes).\n"
        "Then a blank line.\n"
        "Then the post BODY (150–300 words).\n"
        "Do not include any extra headings or markdown beyond plain paragraphs."
    )

    client = _get_client()
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            system_instruction=EDUCATOR_SYSTEM_PROMPT,
            temperature=0.75,
            max_output_tokens=512,
        ),
    )

    text = response.text.strip()
    lines = text.split("\n", 2)
    title = lines[0].strip()
    body = lines[2].strip() if len(lines) >= 3 else (lines[1].strip() if len(lines) >= 2 else "")
    return title, body


async def generate_reply(
    original_post_title: str,
    comment_content: str,
    commenter_name: str,
    model: str,
) -> str:
    """
    Generate a reply to a comment left on one of NeuroBuddy's posts.
    """
    prompt = (
        f"Someone named '{commenter_name}' commented on your post titled "
        f"'{original_post_title}'.\n\n"
        f"Their comment: \"{comment_content}\"\n\n"
        "Write a warm, genuine reply (60–150 words). "
        "Acknowledge their point, add value if possible, and invite further discussion."
    )

    client = _get_client()
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            system_instruction=EDUCATOR_SYSTEM_PROMPT,
            temperature=0.7,
            max_output_tokens=256,
        ),
    )
    return response.text.strip()


async def generate_comment_on_post(
    post_title: str,
    post_content: str,
    author_name: str,
    model: str,
) -> str:
    """
    Generate a thoughtful comment to add value to another agent's relevant post.
    """
    prompt = (
        f"An agent named '{author_name}' posted: \"{post_title}\"\n\n"
        f"Post excerpt: \"{post_content[:600]}\"\n\n"
        "Write a short, thoughtful comment (60–130 words) from the perspective of an "
        "ASD caregiving educator. Add a caregiving angle or share a relevant insight."
    )

    client = _get_client()
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            system_instruction=EDUCATOR_SYSTEM_PROMPT,
            temperature=0.7,
            max_output_tokens=256,
        ),
    )
    return response.text.strip()


async def is_relevant_post(post_title: str, post_content: str, model: str) -> bool:
    """
    Quick relevance check: is this post related to ASD, autism, caregiving,
    mental health, parenting, or sensory topics?
    Returns True if NeuroBuddy should engage with it.
    """
    prompt = (
        f"Post title: \"{post_title}\"\n"
        f"Post excerpt: \"{post_content[:300]}\"\n\n"
        "Is this post related to any of: autism, ASD, caregiving, sensory processing, "
        "special needs, parenting, mental health, or child development?\n"
        "Answer ONLY with: YES or NO"
    )

    client = _get_client()
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            system_instruction=None,
            temperature=0.0,
            max_output_tokens=5,
        ),
    )
    answer = response.text.strip().upper()
    return answer.startswith("Y")


def pick_next_topic(post_count: int) -> str:
    """Return the next topic from the rotation based on how many posts published."""
    return _pick_topic(post_count)


async def generate_introduction(model: str) -> tuple[str, str]:
    """
    Generate a one-time introduction post for m/introductions.
    Returns (title, body).
    """
    prompt = (
        "Write a warm, genuine introduction post for an AI agent named 'anakunggul' "
        "joining the Moltbook community for the first time.\n"
        "anakunggul is an ASD caregiving educator from Indonesia, powered by NeuroDecode AI.\n"
        "The post should:\n"
        "- Introduce who anakunggul is and what their mission is\n"
        "- Mention the focus on supporting caregivers of autistic children\n"
        "- Express genuine interest in learning from other agents on Moltbook\n"
        "- Be warm, humble, and curious — not promotional\n"
        "- 120–200 words\n"
        "Format: first line = post TITLE (max 100 characters, no quotes).\n"
        "Then a blank line.\n"
        "Then the post BODY.\n"
        "No hashtags."
    )
    client = _get_client()
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            system_instruction=EDUCATOR_SYSTEM_PROMPT,
            temperature=0.8,
            max_output_tokens=512,
        ),
    )
    raw = response.text.strip()
    lines = raw.split("\n", 2)
    title = lines[0].strip().lstrip("#").strip()
    body = lines[2].strip() if len(lines) >= 3 else (lines[1].strip() if len(lines) >= 2 else "")
    return title, body


async def generate_dm_reply(
    sender_name: str,
    message_content: str,
    model: str,
) -> str:
    """
    Generate a reply to a private direct message from another agent on Moltbook.
    """
    prompt = (
        f"An AI agent named '{sender_name}' sent you a private message on Moltbook:\n\n"
        f'"{message_content[:500]}"\n\n'
        "Write a friendly, genuine reply (50–120 words) as NeuroBuddy. "
        "Be warm and conversational. If the topic relates to ASD caregiving, "
        "share a useful insight. Otherwise, engage authentically."
    )
    client = _get_client()
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            system_instruction=EDUCATOR_SYSTEM_PROMPT,
            temperature=0.75,
            max_output_tokens=256,
        ),
    )
    return response.text.strip()
