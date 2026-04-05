"""Tool: find_asd_resources — find ASD support resources globally.

- Jakarta / Indonesia: queries the curated NeuroDecode Firestore database (198 resources).
- All other locations: uses Gemini + Google Search grounding for live global results.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_COLLECTION = "clinical_resources"
_FIRESTORE_PROJECT = os.getenv("FIRESTORE_PROJECT", "gen-lang-client-0348071142")
_VALID_TYPES = {"clinic", "therapist", "hospital", "community", "inclusive_school"}

# Keywords that indicate a location covered by the curated Firestore dataset
_CURATED_KEYWORDS = {"jakarta", "indonesia"}


def _is_curated(location: str) -> bool:
    loc = location.strip().lower()
    return any(kw in loc for kw in _CURATED_KEYWORDS)


def _firestore_query(resource_type: str | None, limit: int, location: str) -> dict:
    try:
        from google.cloud import firestore
        from google.cloud.firestore_v1.base_query import FieldFilter

        client = firestore.Client(project=_FIRESTORE_PROJECT)
        ref = client.collection(_COLLECTION)
        ref = ref.where(filter=FieldFilter("is_active", "==", True))
        ref = ref.where(filter=FieldFilter("city", "==", "jakarta"))
        if resource_type and resource_type.lower() in _VALID_TYPES:
            ref = ref.where(filter=FieldFilter("resource_type", "==", resource_type.lower()))

        docs = ref.limit(limit).stream()
        results = []
        for doc in docs:
            d = doc.to_dict() or {}
            results.append({
                "name": d.get("name", ""),
                "resource_type": d.get("resource_type", ""),
                "address": d.get("address", ""),
                "contact": d.get("contact", ""),
                "services": d.get("services", [])[:3],
                "instagram": d.get("instagram", ""),
            })
        return {
            "resources": results,
            "total": len(results),
            "source": "curated",
            "location": location,
        }
    except Exception as exc:
        logger.warning("[find_asd_resources] Firestore query failed: %s", exc)
        return {"resources": [], "total": 0, "source": "curated", "error": str(exc), "location": location}


def _web_search_query(location: str, resource_type: str | None, limit: int) -> dict:
    try:
        from google import genai
        from google.genai import types as genai_types

        type_filter = f" {resource_type}" if resource_type else ""
        prompt = (
            f"List {limit} ASD (autism spectrum disorder) support resources"
            f"{type_filter} in {location}. "
            "For each resource include: organization name, type "
            "(clinic / therapist / school / hospital / community), "
            "address, phone or contact, and key services offered. "
            "Format as a clear numbered list."
        )
        client = genai.Client()
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                tools=[genai_types.Tool(google_search=genai_types.GoogleSearch())],
                temperature=0.1,
            ),
        )
        text = (response.text or "").strip()
        return {
            "resources": [],
            "summary": text,
            "total": 0,
            "source": "web_search",
            "location": location,
            "note": "Results sourced from Google Search via Gemini. Verify contact details before use.",
        }
    except Exception as exc:
        logger.warning("[find_asd_resources] Web search failed: %s", exc)
        return {"resources": [], "total": 0, "source": "web_search", "error": str(exc), "location": location}


def find_asd_resources(
    location: str = "jakarta",
    resource_type: str | None = None,
    limit: int = 10,
) -> dict:
    """
    Find ASD (autism) support resources in any city worldwide.

    For Jakarta and Indonesia: returns verified NeuroDecode curated database
    with 198 clinics, therapists, inclusive schools, hospitals, and community
    centers — real data collected specifically for Indonesian caregivers.

    For all other locations worldwide: performs a live Google Search via Gemini
    to find current ASD support resources in that city.

    Args:
        location: City or location to search in. Examples: 'jakarta', 'singapore',
                  'london', 'new york', 'sydney', 'kuala lumpur'. Default: 'jakarta'.
        resource_type: Filter by type — one of: clinic, therapist, hospital,
                       community, inclusive_school. Omit for all types.
        limit: Maximum number of results to return (1-20). Default: 10.

    Returns:
        For Jakarta/Indonesia — dict with 'resources' list (structured fields:
        name, resource_type, address, contact, services, instagram), 'total',
        'source': 'curated', 'location'.
        For other cities — dict with 'summary' (rich numbered list from Google
        Search), 'source': 'web_search', 'location', 'note'.
    """
    location = (location or "jakarta").strip()
    limit = max(1, min(int(limit), 20))

    if _is_curated(location):
        return _firestore_query(resource_type, limit, location)
    else:
        return _web_search_query(location, resource_type, limit)
