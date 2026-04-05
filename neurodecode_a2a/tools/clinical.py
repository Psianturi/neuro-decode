"""Tool: find_local_resources — query clinical_resources/ Firestore collection."""
from __future__ import annotations

import os
import logging
from typing import Any

logger = logging.getLogger(__name__)

_COLLECTION = "clinical_resources"
_FIRESTORE_PROJECT = os.getenv("FIRESTORE_PROJECT", "gen-lang-client-0348071142")

_VALID_TYPES = {"clinic", "therapist", "hospital", "community", "inclusive_school"}


def _get_client() -> Any | None:
    try:
        from google.cloud import firestore
        from google.cloud.firestore_v1.base_query import FieldFilter
        return firestore.Client(project=_FIRESTORE_PROJECT), FieldFilter
    except Exception as exc:
        logger.warning("[clinical] Firestore unavailable: %s", exc)
        return None, None


def find_local_resources(
    city: str = "jakarta",
    resource_type: str | None = None,
    limit: int = 10,
) -> dict:
    """
    Find ASD-relevant clinics, therapists, schools, hospitals, and community
    centers in the specified city.

    Args:
        city: City to search in. Currently supported: 'jakarta'. Default: 'jakarta'.
        resource_type: Filter by type — one of: clinic, therapist, hospital,
                       community, inclusive_school. Omit for all types.
        limit: Maximum number of results to return (1-20). Default: 10.

    Returns:
        A dict with 'resources' list and 'total' count.
    """
    city = city.strip().lower() or "jakarta"
    limit = max(1, min(int(limit), 20))

    client, FieldFilter = _get_client()
    if client is None:
        return {"resources": [], "total": 0, "error": "Database unavailable"}

    try:
        from google.cloud import firestore as fs
        ref = client.collection(_COLLECTION)
        ref = ref.where(filter=FieldFilter("is_active", "==", True))
        ref = ref.where(filter=FieldFilter("city", "==", city))
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

        return {"resources": results, "total": len(results), "city": city}

    except Exception as exc:
        logger.warning("[clinical] Query failed: %s", exc)
        return {"resources": [], "total": 0, "error": str(exc)}
