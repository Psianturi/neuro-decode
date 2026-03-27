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
import time as _time_module
from typing import Literal

from google import genai
from google.genai import types as genai_types

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Persona system prompt
# ---------------------------------------------------------------------------

EDUCATOR_SYSTEM_PROMPT = """\
You are NeuroBuddy, a warm and intellectually curious neurodiversity educator on Moltbook — \
a social platform for AI agents.

Your core focus is autism spectrum disorder (ASD) and neurodiversity, but you engage \
broadly with caregiving, mental health, child development, education policy, and society. \
You care deeply about the humans behind every caregiving story.

Your mission: share genuinely useful, thought-provoking content that serves caregivers, \
autistic individuals, educators, and anyone curious about the neurodivergent mind.

RULES:
- Write with warmth, intellectual depth, and originality. Never sound like a content farm.
- Bring a fresh, specific angle — if a topic was covered recently, find a new entry point.
- You may name real public figures (Temple Grandin, Greta Thunberg, etc.) when genuinely relevant.
- You may connect topics to broader conversations: AI, remote work, education reform, pop culture.
- Write in English. Never diagnose, prescribe, or replace professional medical advice.
- Never reference private user data, sensor readings, or unnamed real children.
- Do not fabricate statistics. Use phrases like "research suggests" or "clinicians often observe."
- Posts: 180–320 words. Comments/replies: 60–130 words.
- No hashtags. Minimal emojis. No marketing language.
- Do NOT mention NeuroDecode the app or repository unless directly asked.
- Be a genuine community member, not a broadcast channel.
"""

# Topics the Educator rotates through
EDUCATOR_TOPICS = [
    # Core ASD caregiving
    "the difference between a meltdown and a shutdown — why it matters for caregivers",
    "how to build a visual schedule that actually works for your child",
    "communication bridges: what to do when words feel impossible during crisis moments",
    "understanding demand avoidance (PDA) — the part of autism many caregivers miss",
    "sleep challenges in autism: what the research says and what actually helps",
    "sensory diets: how to work with an OT to design one that fits your child's life",
    "navigating IEP meetings: practical strategies to advocate effectively for your child",
    "AAC tools for non-speaking or minimally verbal autistic individuals",
    "food selectivity in autism — practical approaches beyond just 'try new foods'",
    "sibling dynamics in ASD families: how to support the neurotypical child too",
    "preventing caregiver burnout: what self-care actually looks like under real pressure",
    "using your child's special interest as a teaching and bonding bridge",
    # Broader neurodiversity + society
    "Temple Grandin's lifetime of work — and what her legacy means for autism today",
    "Greta Thunberg and autism: when neurodiversity changes the world",
    "late diagnosis in adulthood: what it means to discover you are autistic at 30 or 40",
    "autism and gender: why women and girls are so often missed in diagnosis",
    "the neurodiversity movement: what it gets right and where the debates still rage",
    "neurodiversity at work: what employers get wrong — and the companies doing it right",
    "how autism representation in film and TV has evolved (and where it still falls short)",
    "the mental health crisis among autistic adults — loneliness, anxiety, and what helps",
    "masking in autism: what it costs children and adults who hide who they are",
    "how schools can become genuinely inclusive — beyond ramps and quiet rooms",
    # Intersection with current events & technology
    "how AI tools are quietly transforming daily life for some autistic individuals",
    "remote work and autism: an unexpected benefit of the pandemic-era shift",
    "social media and the autistic brain: community, overload, and finding balance",
    "mindfulness for autistic children: adapting practices for sensory sensitivities",
    "the loneliness epidemic and autism: connection in an overstimulating world",
    "from stigma to acceptance: how Indonesia and Southeast Asia are catching up on autism awareness",
    "preparing autistic children for disruption: how to handle unexpected changes",
    "what caregivers wish other people understood about their daily life",
    "positive behavior support: moving away from compliance toward genuine wellbeing",
    "the science of co-regulation: why a caregiver's calm is the most powerful tool",
]


def _pick_topic(post_count: int) -> str:
    # Mix post_count with a time bucket so cold-start resets (post_count=0)
    # don't always land on the same topic. Rotates every 4 hours.
    time_bucket = int(_time_module.time() // (3600 * 4))
    return EDUCATOR_TOPICS[(post_count + time_bucket) % len(EDUCATOR_TOPICS)]


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
    from datetime import date
    today = date.today().strftime("%B %Y")
    prompt = (
        f"Today is {today}. Write an original, insightful post on this topic: {topic}.\n"
        "Requirements:\n"
        "- Bring a specific, fresh angle — not generic advice people have heard a hundred times.\n"
        "- If relevant, reference real people, recent trends, or concrete examples.\n"
        "- Do NOT open the body with the same words as the title.\n"
        "Format:\n"
        "  Line 1: TITLE (max 120 characters, plain text, no quotes, no markdown)\n"
        "  Line 2: (blank)\n"
        "  Line 3+: BODY (180–300 words, plain paragraphs, no headers, no bullet lists)\n"
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
