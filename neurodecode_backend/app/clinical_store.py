"""clinical_store.py — Phase 4 Clinical Routing.

Manages the `clinical_resources` Firestore collection.

Schema per document
-------------------
{
  "name": str,                  # Display name, e.g. "Anak Unggul"
  "resource_type": str,         # "clinic" | "therapist" | "hospital" |
                                #  "community" | "inclusive_school" | "other"
    "source": str,                # "curated" | "live_search"
  "city": str,                  # lowercase city slug, e.g. "jakarta"
  "address": str,               # Street / area detail, e.g. "Sunter, Jakarta Utara"
  "contact": str,               # Primary phone / WhatsApp
  "instagram": str,             # Instagram handle without @, or empty string
  "services": list[str],        # e.g. ["therapy", "assessment", "homeschooling"]
  "specialization": list[str],  # ["ASD", "ADHD", "sensory", "speech"]
  "is_active": bool,
  "last_verified_date": str,    # ISO date "YYYY-MM-DD" — staleness guard (ADR-001)
  "verified_by": str,           # admin uid or "seed"
  "created_at": str,            # ISO datetime UTC
  "updated_at": str,            # ISO datetime UTC
}
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_stale(last_verified_date: str | None, threshold_days: int = 365) -> bool:
    """Return True if the resource has not been verified within threshold_days."""
    if not last_verified_date:
        return True
    try:
        verified = datetime.fromisoformat(last_verified_date).replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - verified).days
        return age > threshold_days
    except ValueError:
        return True


def _normalize_source(value: Any) -> str:
    raw = str(value or "").strip().lower().replace("-", "_")
    if raw in {"curated", "live_search"}:
        return raw
    return "curated"


# --------------------------------------------------------------------------- #
# ClinicalStore
# --------------------------------------------------------------------------- #

class ClinicalStore:
    def __init__(self, db: Any, collection: str) -> None:
        self._db = db
        self._col = collection

    # ---------------------------------------------------------------------- #
    # read
    # ---------------------------------------------------------------------- #

    def list_resources(
        self,
        *,
        city: str | None = None,
        resource_type: str | None = None,
        active_only: bool = True,
        limit: int = 50,
    ) -> list[dict]:
        """Return clinical resources, optionally filtered by city / type."""
        ref = self._db.collection(self._col)

        try:
            from google.cloud.firestore_v1.base_query import FieldFilter as _FF
        except ImportError:
            _FF = None

        def _where(ref, field, value):
            if _FF is not None:
                return ref.where(filter=_FF(field, "==", value))
            return ref.where(field, "==", value)

        if active_only:
            ref = _where(ref, "is_active", True)
        if city:
            ref = _where(ref, "city", city.lower())
        if resource_type:
            ref = _where(ref, "resource_type", resource_type.lower())

        docs = ref.limit(limit).stream()
        results = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            data["stale"] = _is_stale(data.get("last_verified_date"))
            data["source"] = _normalize_source(data.get("source"))
            results.append(data)

        return results

    def get_resource(self, resource_id: str) -> dict | None:
        """Return a single resource by document ID."""
        doc = self._db.collection(self._col).document(resource_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        data["id"] = doc.id
        data["stale"] = _is_stale(data.get("last_verified_date"))
        data["source"] = _normalize_source(data.get("source"))
        return data

    # ---------------------------------------------------------------------- #
    # write
    # ---------------------------------------------------------------------- #

    def create_resource(self, payload: dict) -> str:
        """Create a new resource. Returns the generated document ID."""
        now = _now_iso()
        doc = {
            "name": str(payload.get("name", "")).strip(),
            "resource_type": str(payload.get("resource_type", "")).lower().strip(),
            "source": _normalize_source(payload.get("source")),
            "city": str(payload.get("city", "")).lower().strip(),
            "address": str(payload.get("address", "")).strip(),
            "contact": str(payload.get("contact", "")).strip(),
            "instagram": str(payload.get("instagram", "")).strip().lstrip("@"),
            "services": list(payload.get("services") or []),
            "specialization": list(payload.get("specialization") or []),
            "is_active": bool(payload.get("is_active", True)),
            "last_verified_date": str(payload.get("last_verified_date", now[:10])),
            "verified_by": str(payload.get("verified_by", "seed")).strip(),
            "created_at": now,
            "updated_at": now,
        }
        _ref = self._db.collection(self._col).document()
        _ref.set(doc)
        logger.info("clinical_store: created resource %s (%s)", _ref.id, doc["name"])
        return _ref.id

    def upsert_resource(self, place_id: str, payload: dict) -> str:
        """Insert or update a resource keyed by Google place_id.

        Uses Firestore set-with-merge so re-running the harvest script is
        idempotent — existing manual edits (e.g. is_active=False) are NOT
        overwritten for fields not present in payload.
        """
        now = _now_iso()
        doc = {
            "name": str(payload.get("name", "")).strip(),
            "resource_type": str(payload.get("resource_type", "")).lower().strip(),
            "source": _normalize_source(payload.get("source")),
            "city": str(payload.get("city", "")).lower().strip(),
            "address": str(payload.get("address", "")).strip(),
            "contact": str(payload.get("contact", "")).strip(),
            "instagram": str(payload.get("instagram", "")).strip().lstrip("@"),
            "services": list(payload.get("services") or []),
            "specialization": list(payload.get("specialization") or []),
            "place_id": place_id,
            "is_active": bool(payload.get("is_active", True)),
            "last_verified_date": str(payload.get("last_verified_date", now[:10])),
            "verified_by": str(payload.get("verified_by", "harvest_places")).strip(),
            "updated_at": now,
        }
        ref = self._db.collection(self._col).document(place_id)
        if not ref.get().exists:
            doc["created_at"] = now
            ref.set(doc)
            logger.info("clinical_store: inserted place %s (%s)", place_id, doc["name"])
        else:
            # preserve created_at; skip is_active so manual deactivation survives
            doc.pop("is_active", None)
            ref.update(doc)
            logger.info("clinical_store: updated place %s (%s)", place_id, doc["name"])
        return place_id

    def update_resource(self, resource_id: str, payload: dict) -> bool:
        """Partial update. Returns False if document not found."""
        ref = self._db.collection(self._col).document(resource_id)
        if not ref.get().exists:
            return False

        allowed_fields = {
            "name", "resource_type", "city", "address", "contact",
            "instagram", "services", "specialization",
            "is_active", "last_verified_date", "verified_by",
        }
        updates = {k: v for k, v in payload.items() if k in allowed_fields}
        updates["updated_at"] = _now_iso()
        ref.update(updates)
        logger.info("clinical_store: updated resource %s", resource_id)
        return True
