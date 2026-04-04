"""seed_clinical_resources.py — Seed initial clinical resource entries.

Run from repo root:
    python neurodecode_backend/scripts/seed_clinical_resources.py

Requires GOOGLE_APPLICATION_CREDENTIALS or ADC pointing to the GCP project.
"""

import asyncio
import sys
import os

# Allow importing app modules from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.clinical_store import ClinicalStore  # noqa: E402

RESOURCES = [
    # ── Anak Unggul ─────────────────────────────────────────────────────────
    {
        "name": "Anak Unggul - Sunter",
        "resource_type": "inclusive_school",
        "city": "jakarta",
        "address": "Sunter, Jakarta Utara",
        "contact": "082122004252",
        "instagram": "anak_unggul",
        "services": [
            "inclusive PAUD",
            "homeschooling",
            "therapy",
            "tutoring",
            "psychology consultation",
            "IQ test",
            "assessment",
            "home visit",
            "skills training",
        ],
        "specialization": ["ASD", "special needs", "inclusive education"],
        "is_active": True,
        "last_verified_date": "2026-04-04",
        "verified_by": "seed_manual",
    },
    {
        "name": "Anak Unggul - Kelapa Gading",
        "resource_type": "inclusive_school",
        "city": "jakarta",
        "address": "Kelapa Gading, Jakarta Utara",
        "contact": "089679097295",
        "instagram": "anak_unggul",
        "services": [
            "inclusive PAUD",
            "homeschooling",
            "therapy",
            "tutoring",
            "psychology consultation",
            "IQ test",
            "assessment",
            "home visit",
            "skills training",
        ],
        "specialization": ["ASD", "special needs", "inclusive education"],
        "is_active": True,
        "last_verified_date": "2026-04-04",
        "verified_by": "seed_manual",
    },
]


async def main() -> None:
    store = ClinicalStore()
    for resource in RESOURCES:
        doc_id = await store.create_resource(resource)
        print(f"Created: {doc_id}  ({resource['name']})")
    print(f"\nSeeded {len(RESOURCES)} resource(s).")


if __name__ == "__main__":
    asyncio.run(main())
