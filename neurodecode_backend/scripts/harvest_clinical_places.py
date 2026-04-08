"""harvest_clinical_places.py — Harvest ASD-related clinical resources for Jakarta
from Google Places API (New) and upsert into Firestore clinical_resources/.

Based on: https://developers.google.com/maps/documentation/places/web-service/text-search

Usage:
    c:/PROJ/NeuroDecode/.venv/Scripts/python.exe neurodecode_backend/scripts/harvest_clinical_places.py
    c:/PROJ/NeuroDecode/.venv/Scripts/python.exe neurodecode_backend/scripts/harvest_clinical_places.py --cities "jakarta,medan,surabaya"
    c:/PROJ/NeuroDecode/.venv/Scripts/python.exe neurodecode_backend/scripts/harvest_clinical_places.py --cities "new york,singapore" --country ""

Requires:
    neurodecode_backend/.env  with PLACES_API_KEY_NEW (primary)
                              and  PLACES_API_KEY      (fallback to old API)
    Google ADC for Firestore: gcloud auth application-default login


"""

import asyncio
import argparse
import logging
import os
import sys
import time
from datetime import date
from pathlib import Path

import httpx
from dotenv import load_dotenv

# ── path setup ──────────────────────────────────────────────────────────────
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND_ROOT))

load_dotenv(_BACKEND_ROOT / ".env")

from app.clinical_store import ClinicalStore  # noqa: E402

# ── logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger("harvest")

# ── API config ───────────────────────────────────────────────────────────────
_KEY_NEW = os.getenv("PLACES_API_KEY_NEW", "")
_KEY_OLD = os.getenv("PLACES_API_KEY", "")

_PLACES_NEW_URL = "https://places.googleapis.com/v1/places:searchText"
_PLACES_OLD_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"

# Known city config for stronger geo precision and old API fallback.
_CITY_PRESETS = {
    "jakarta": {
        "region": "ID",
        "language": "id",
        "location_restriction": {
            "rectangle": {
                "low": {"latitude": -6.37, "longitude": 106.68},
                "high": {"latitude": -6.08, "longitude": 106.97},
            }
        },
        "old_location": "-6.2,106.82",
        "old_radius": 35000,
    },
    "medan": {
        "region": "ID",
        "language": "id",
        "location_restriction": {
            "rectangle": {
                "low": {"latitude": 3.45, "longitude": 98.55},
                "high": {"latitude": 3.75, "longitude": 98.80},
            }
        },
        "old_location": "3.5952,98.6722",
        "old_radius": 25000,
    },
    "surabaya": {
        "region": "ID",
        "language": "id",
        "location_restriction": {
            "rectangle": {
                "low": {"latitude": -7.40, "longitude": 112.58},
                "high": {"latitude": -7.17, "longitude": 112.88},
            }
        },
        "old_location": "-7.2575,112.7521",
        "old_radius": 25000,
    },
    "bandung": {
        "region": "ID",
        "language": "id",
        "location_restriction": {
            "rectangle": {
                "low": {"latitude": -6.99, "longitude": 107.49},
                "high": {"latitude": -6.80, "longitude": 107.75},
            }
        },
        "old_location": "-6.9175,107.6191",
        "old_radius": 22000,
    },
    "yogyakarta": {
        "region": "ID",
        "language": "id",
        "old_location": "-7.7956,110.3695",
        "old_radius": 22000,
    },
    "makassar": {
        "region": "ID",
        "language": "id",
        "old_location": "-5.1477,119.4327",
        "old_radius": 28000,
    },
    "bangkok": {
        "region": "TH",
        "language": "en",
        "old_location": "13.7563,100.5018",
        "old_radius": 30000,
    },
    "new york": {
        "region": "US",
        "language": "en",
    },
    "singapore": {
        "region": "SG",
        "language": "en",
    },
    "kuala lumpur": {
        "region": "MY",
        "language": "en",
    },
}

# FieldMask — comma-separated, NO spaces allowed per docs
# Includes Enterprise fields (nationalPhoneNumber) for phone data
_FIELD_MASK = ",".join([
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.nationalPhoneNumber",
    "places.primaryType",
    "places.types",
    "nextPageToken",
])

# ── search query templates (expanded per city) ──────────────────────────────
_QUERY_TEMPLATES_ID = [
    "klinik terapi autisme {city}",
    "terapis ASD anak {city}",
    "sekolah inklusi autisme {city}",
    "speech therapy anak {city}",
    "occupational therapy anak {city}",
    "psikolog anak autisme {city}",
    "pusat terapi anak berkebutuhan khusus {city}",
    "homeschooling autisme {city}",
    "klinik tumbuh kembang anak {city}",
    "autism center {city}",
]

_QUERY_TEMPLATES_GLOBAL = [
    "autism clinic {city}",
    "ASD therapist {city}",
    "autism center {city}",
    "speech therapy autism {city}",
    "occupational therapy autism {city}",
    "child psychologist autism {city}",
    "special education autism {city}",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Harvest ASD clinical resources into Firestore")
    parser.add_argument(
        "--cities",
        default="jakarta",
        help="Comma-separated cities, e.g. 'jakarta,medan,surabaya'",
    )
    parser.add_argument(
        "--country",
        default="",
        help="Optional country suffix for queries, e.g. 'Indonesia' or 'United States'",
    )
    parser.add_argument(
        "--max-queries-per-city",
        type=int,
        default=0,
        help="Optional cap for query count per city (0 = all templates)",
    )
    return parser.parse_args()


def _parse_cities(raw: str) -> list[str]:
    out: list[str] = []
    seen = set()
    for part in (raw or "jakarta").split(","):
        city = part.strip()
        if not city:
            continue
        key = city.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(city)
    return out or ["jakarta"]


def _city_profile(city: str) -> dict:
    key = city.lower().strip()
    base = _CITY_PRESETS.get(key, {})
    if base:
        return dict(base)
    return {
        "region": "",
        "language": "en",
    }


def _queries_for_city(city: str, country: str, region: str, max_queries: int) -> list[str]:
    city_phrase = city if not country else f"{city}, {country}"
    templates = _QUERY_TEMPLATES_ID if region == "ID" else _QUERY_TEMPLATES_GLOBAL
    queries = [tpl.format(city=city_phrase) for tpl in templates]
    if max_queries > 0:
        return queries[:max_queries]
    return queries

# ── resource type inference from Google place types ──────────────────────────
_SCHOOL_TYPES = {"school", "primary_school", "secondary_school", "preschool", "university"}
_HOSPITAL_TYPES = {"hospital"}
_THERAPIST_TYPES = {"physiotherapist", "psychologist", "mental_health"}

def _infer_resource_type(google_types: list[str]) -> str:
    t = set(google_types)
    if t & _SCHOOL_TYPES:
        return "inclusive_school"
    if t & _HOSPITAL_TYPES:
        return "hospital"
    if t & _THERAPIST_TYPES:
        return "therapist"
    return "clinic"


def _today() -> str:
    return date.today().isoformat()


# ── Places API (New) — single page ───────────────────────────────────────────
async def _fetch_page_new(
    client: httpx.AsyncClient,
    query: str,
    location_restriction: dict | None,
    language_code: str,
    region_code: str,
    page_token: str | None = None,
) -> tuple[list[dict], str | None]:
    """Fetch one page from Places API (New) Text Search.

    Returns (places_list, next_page_token_or_None).
    """
    body: dict = {
        "textQuery": query,
        "pageSize": 20,                           # max per page per docs
        "languageCode": language_code or "en",
    }
    if region_code:
        body["regionCode"] = region_code
    if location_restriction:
        body["locationRestriction"] = location_restriction
    if page_token:
        body["pageToken"] = page_token

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": _KEY_NEW,
        "X-Goog-FieldMask": _FIELD_MASK,
    }

    resp = await client.post(_PLACES_NEW_URL, json=body, headers=headers, timeout=20)

    if resp.status_code != 200:
        log.warning("Places API (New) HTTP %s for '%s': %s",
                    resp.status_code, query, resp.text[:300])
        return [], None

    data = resp.json()
    places = data.get("places", [])
    next_token = data.get("nextPageToken")
    return places, next_token


async def _search_new_all_pages(
    client: httpx.AsyncClient,
    query: str,
    location_restriction: dict | None,
    language_code: str,
    region_code: str,
) -> list[dict]:
    """Fetch all pages (up to 60 results max per docs) for a query."""
    all_places: list[dict] = []
    page_token: str | None = None
    page_num = 0

    while True:
        page_num += 1
        places, next_token = await _fetch_page_new(
            client,
            query,
            location_restriction,
            language_code,
            region_code,
            page_token,
        )
        all_places.extend(places)
        log.info("    page %d: %d results (total so far: %d)", page_num, len(places), len(all_places))

        if not next_token or len(all_places) >= 60:
            break

        page_token = next_token
        await asyncio.sleep(0.3)   # brief pause between pages

    return all_places


# ── Places API (old) — fallback, single page only ───────────────────────────
async def _search_old(
    client: httpx.AsyncClient,
    query: str,
    old_location: str | None,
    old_radius: int,
    language_code: str,
) -> list[dict]:
    """Call Places API (old) Text Search. Returns raw results list."""
    params = {
        "query": query,
        "key": _KEY_OLD,
        "language": language_code or "en",
    }
    if old_location:
        params["location"] = old_location
        params["radius"] = old_radius
    resp = await client.get(_PLACES_OLD_URL, params=params, timeout=20)
    if resp.status_code != 200:
        log.warning("Places API (old) HTTP %s for '%s'", resp.status_code, query)
        return []
    data = resp.json()
    status = data.get("status", "")
    if status not in ("OK", "ZERO_RESULTS"):
        log.warning("Places API (old) status '%s' for '%s'", status, query)
        return []
    return data.get("results", [])


# ── normalize to our schema ──────────────────────────────────────────────────
def _normalize_new(place: dict, city: str) -> tuple[str, dict] | None:
    """Map Places API (New) response → (place_id, payload). Returns None if invalid."""
    place_id = place.get("id", "").strip()
    if not place_id:
        return None

    name = (place.get("displayName") or {}).get("text", "").strip()
    if not name:
        return None

    address = place.get("formattedAddress", "").strip()
    phone = place.get("nationalPhoneNumber", "").strip()
    google_types = place.get("types", [])

    payload = {
        "name": name,
        "resource_type": _infer_resource_type(google_types),
        "city": city.lower().strip(),
        "address": address,
        "contact": phone,
        "instagram": "",
        "services": [],
        "specialization": ["ASD"],
        "is_active": True,
        "last_verified_date": _today(),
        "verified_by": "harvest_places_new",
    }
    return place_id, payload


def _normalize_old(place: dict, city: str) -> tuple[str, dict] | None:
    """Map Places API (old) response → (place_id, payload). Returns None if invalid."""
    place_id = place.get("place_id", "").strip()
    name = place.get("name", "").strip()
    if not place_id or not name:
        return None

    address = place.get("formatted_address", "").strip()
    google_types = place.get("types", [])

    payload = {
        "name": name,
        "resource_type": _infer_resource_type(google_types),
        "city": city.lower().strip(),
        "address": address,
        "contact": "",
        "instagram": "",
        "services": [],
        "specialization": ["ASD"],
        "is_active": True,
        "last_verified_date": _today(),
        "verified_by": "harvest_places_old",
    }
    return place_id, payload


# ── main ─────────────────────────────────────────────────────────────────────
async def main() -> None:
    args = _parse_args()
    cities = _parse_cities(args.cities)

    if not _KEY_NEW and not _KEY_OLD:
        log.error("No API keys found. Set PLACES_API_KEY_NEW or PLACES_API_KEY in .env")
        sys.exit(1)

    log.info("Keys — Places (New): %s | Places (old): %s", bool(_KEY_NEW), bool(_KEY_OLD))

    from google.cloud import firestore as _fs
    gcp_project = os.getenv("GOOGLE_CLOUD_PROJECT", "gen-lang-client-0348071142")
    db = _fs.Client(project=gcp_project)
    store = ClinicalStore(db=db, collection="clinical_resources")

    seen_ids: set[str] = set()
    inserted = 0
    updated = 0
    skipped = 0

    async with httpx.AsyncClient() as client:
        for city in cities:
            profile = _city_profile(city)
            region = profile.get("region", "")
            language = profile.get("language", "en")
            location_restriction = profile.get("location_restriction")
            old_location = profile.get("old_location")
            old_radius = int(profile.get("old_radius", 35000))
            queries = _queries_for_city(city, args.country, region, args.max_queries_per_city)

            log.info("")
            log.info("=== Target city: %s | region=%s | queries=%d ===", city, region or "(none)", len(queries))

            for query in queries:
                log.info("Searching: '%s'", query)
                normalized: list[tuple[str, dict]] = []

                # Primary: Places API (New) with pagination
                if _KEY_NEW:
                    raw_places = await _search_new_all_pages(
                        client,
                        query,
                        location_restriction,
                        language,
                        region,
                    )
                    for p in raw_places:
                        result = _normalize_new(p, city)
                        if result:
                            normalized.append(result)
                    log.info("  → %d valid results (Places New)", len(normalized))

                # Fallback: old API (single page) if New returned nothing
                if not normalized and _KEY_OLD:
                    raw_old = await _search_old(client, query, old_location, old_radius, language)
                    for p in raw_old:
                        result = _normalize_old(p, city)
                        if result:
                            normalized.append(result)
                    log.info("  → %d valid results (Places old, fallback)", len(normalized))

                for place_id, payload in normalized:
                    if place_id in seen_ids:
                        skipped += 1
                        continue
                    seen_ids.add(place_id)

                    existing = store.get_resource(place_id)
                    store.upsert_resource(place_id, payload)
                    if existing:
                        updated += 1
                    else:
                        inserted += 1

                # Polite delay between queries to avoid rate limiting
                time.sleep(0.5)

    log.info("")
    log.info("── Harvest complete ──────────────────────────")
    log.info("  Inserted : %d new resources", inserted)
    log.info("  Updated  : %d existing resources", updated)
    log.info("  Skipped  : %d (no id/name or duplicate within run)", skipped)
    log.info("  Total unique places processed: %d", inserted + updated)
    log.info("  Firestore collection: clinical_resources/")
    log.info("  Target cities: %s", ", ".join(cities))


if __name__ == "__main__":
    asyncio.run(main())
