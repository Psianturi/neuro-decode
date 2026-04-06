"""Tool: find_asd_resources — find ASD support resources globally.

- Jakarta / Indonesia: queries the curated NeuroDecode Firestore database (198 resources).
- All other locations: uses Gemini + Google Search grounding for live global results.

Cost controls:
- In-memory cache (24h TTL) — prevents duplicate Gemini+Search calls for same location
- Firestore persistent cache — survives cold starts, shared across instances
- Rate limit: max 15 web searches per location per hour
"""
from __future__ import annotations

import logging
import os
import time

logger = logging.getLogger(__name__)

_COLLECTION = "clinical_resources"
_CACHE_COLLECTION = "a2a_resource_cache"
_FIRESTORE_PROJECT = os.getenv("FIRESTORE_PROJECT", "gen-lang-client-0348071142")
_VALID_TYPES = {"clinic", "therapist", "hospital", "community", "inclusive_school"}
_CURATED_KEYWORDS = {"jakarta", "indonesia"}

# In-memory cache: location_key → (result_dict, timestamp)
_mem_cache: dict[str, tuple[dict, float]] = {}
_CACHE_TTL = 86400.0  # 24 hours

# Rate limit: location_key → list of call timestamps in current window
_rate_window: dict[str, list[float]] = {}
_RATE_LIMIT = 15        # max web searches per location
_RATE_WINDOW = 3600.0  # per hour


def _cache_key(location: str, resource_type: str) -> str:
    return f"{location.lower().strip()}:{resource_type or 'all'}"


def _get_mem_cache(key: str) -> dict | None:
    if key in _mem_cache:
        result, ts = _mem_cache[key]
        if time.time() - ts < _CACHE_TTL:
            return result
        del _mem_cache[key]
    return None


def _set_mem_cache(key: str, result: dict) -> None:
    _mem_cache[key] = (result, time.time())


def _is_rate_limited(location_key: str) -> bool:
    now = time.time()
    calls = _rate_window.get(location_key, [])
    # Drop calls outside the window
    calls = [t for t in calls if now - t < _RATE_WINDOW]
    _rate_window[location_key] = calls
    return len(calls) >= _RATE_LIMIT


def _record_call(location_key: str) -> None:
    calls = _rate_window.get(location_key, [])
    calls.append(time.time())
    _rate_window[location_key] = calls


def _get_firestore_cache(key: str) -> dict | None:
    """Check Firestore persistent cache — survives cold starts."""
    try:
        from google.cloud import firestore
        client = firestore.Client(project=_FIRESTORE_PROJECT)
        doc = client.collection(_CACHE_COLLECTION).document(key.replace("/", "_")).get()
        if not doc.exists:
            return None
        d = doc.to_dict() or {}
        cached_at = d.get("cached_at", 0.0)
        if time.time() - float(cached_at) < _CACHE_TTL:
            return d.get("result")
    except Exception:
        pass
    return None


def _set_firestore_cache(key: str, result: dict) -> None:
    """Persist result to Firestore cache. Best-effort, non-blocking."""
    try:
        from google.cloud import firestore
        client = firestore.Client(project=_FIRESTORE_PROJECT)
        client.collection(_CACHE_COLLECTION).document(key.replace("/", "_")).set({
            "result": result,
            "cached_at": time.time(),
            "location_key": key,
        })
    except Exception as exc:
        logger.debug("[find_asd_resources] Firestore cache write failed: %s", exc)


def _is_curated(location: str) -> bool:
    loc = location.strip().lower()
    return any(kw in loc for kw in _CURATED_KEYWORDS)


def _firestore_query(resource_type: str, limit: int, location: str) -> dict:
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


def _web_search_query(location: str, resource_type: str, limit: int) -> dict:
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
    location: str,
    resource_type: str,
    limit: str,
):
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
                       community, inclusive_school. Leave empty for all types.
        limit: Maximum number of results to return (1-20). Default: 10.

    Returns:
        For Jakarta/Indonesia — dict with 'resources' list (structured fields:
        name, resource_type, address, contact, services, instagram), 'total',
        'source': 'curated', 'location'.
        For other cities — dict with 'summary' (rich numbered list from Google
        Search), 'source': 'web_search', 'location', 'note'.
    """
    location = (location or "jakarta").strip()
    rtype = (resource_type or "").strip()
    limit = max(1, min(int(limit or "10"), 20))
    key = _cache_key(location, rtype)

    if _is_curated(location):
        return _firestore_query(rtype, limit, location)

    cached = _get_mem_cache(key)
    if cached:
        logger.info("[find_asd_resources] mem cache hit: %s", key)
        return {**cached, "cached": True}

    cached = _get_firestore_cache(key)
    if cached:
        logger.info("[find_asd_resources] Firestore cache hit: %s", key)
        _set_mem_cache(key, cached)
        return {**cached, "cached": True}

    if _is_rate_limited(key):
        logger.warning("[find_asd_resources] Rate limit hit for: %s", key)
        return {
            "resources": [],
            "total": 0,
            "source": "rate_limited",
            "location": location,
            "note": "Too many requests for this location. Please try again in an hour.",
        }

    _record_call(key)
    result = _web_search_query(location, rtype, limit)

    if "error" not in result:
        _set_mem_cache(key, result)
        _set_firestore_cache(key, result)

    return result
