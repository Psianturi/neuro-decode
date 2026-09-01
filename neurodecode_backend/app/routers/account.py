from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from urllib import parse as urlparse
from urllib import request as urlrequest

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_uid
from app.state import settings

try:
    from google.cloud import firestore
except Exception:
    firestore = None

router = APIRouter()

_LEGACY_CLAIMS_COLLECTION = "legacy_claims"

_client: Any | None = None


def _get_client():
    global _client
    if firestore is None:
        raise RuntimeError("google-cloud-firestore not installed")
    if _client is None:
        _client = firestore.Client(project=settings.firestore_project)
    return _client


def _notify_conflict(legacy_user_id: str, attempted_uid: str) -> None:
    """Best-effort Telegram alert on a legacy-claim conflict — reuses the same
    bot/chat already configured for session-summary alerts elsewhere in this
    codebase, so a possible takeover attempt during the trusted window is at
    least visible in real time."""
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return
    text = (
        "NeuroDecode legacy-claim conflict\n"
        f"legacy_user_id={legacy_user_id}\n"
        f"attempted_by_uid={attempted_uid}\n"
        "This legacy id was already claimed by a different identity — "
        "possible race or takeover attempt during the trusted migration window."
    )
    try:
        api_url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
        payload = {"chat_id": settings.telegram_chat_id, "text": text}
        encoded = urlparse.urlencode(payload).encode("utf-8")
        req = urlrequest.Request(api_url, data=encoded, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urlrequest.urlopen(req, timeout=10) as resp:
            if resp.status >= 300:
                print(f"[account] telegram conflict alert failed with status {resp.status}")
    except Exception as e:
        print(f"[account] telegram conflict alert failed: {e}")


def _acquire_or_resume_claim(client, legacy_user_id: str, new_uid: str) -> str:
    """Returns 'proceed' | 'already_complete' | 'conflict'.

    Uses Firestore's atomic document create() as the lock: the first caller to
    successfully create the claim doc wins. A caller that already holds the
    claim (same uid, e.g. retrying after a crash mid-migration) is allowed to
    resume rather than being rejected — this is the fix for the earlier design
    where the lock alone was mistaken for "migration complete."
    """
    doc_ref = client.collection(_LEGACY_CLAIMS_COLLECTION).document(legacy_user_id)
    now = datetime.now(timezone.utc).isoformat()
    try:
        doc_ref.create(
            {
                "status": "in_progress",
                "claimed_by_uid": new_uid,
                "claimed_at": now,
                "completed_at": None,
            }
        )
        return "proceed"
    except Exception:
        pass

    snapshot = doc_ref.get()
    data = snapshot.to_dict() or {}
    if data.get("claimed_by_uid") != new_uid:
        return "conflict"
    if data.get("status") == "complete":
        return "already_complete"
    return "proceed"


def _mark_complete(client, legacy_user_id: str) -> None:
    client.collection(_LEGACY_CLAIMS_COLLECTION).document(legacy_user_id).set(
        {"status": "complete", "completed_at": datetime.now(timezone.utc).isoformat()},
        merge=True,
    )


def _rekey_collection_by_field(client, collection_name: str, legacy_user_id: str, new_uid: str) -> int:
    """Batch-rewrite the `user_id` field on every doc in a flat collection that
    still has the legacy id. Idempotent by construction: once a doc's user_id
    has been rewritten, a re-run's query no longer matches it, so re-running
    this after a crash simply picks up wherever it left off with no duplicate
    writes and no special cursor bookkeeping needed at this data volume."""
    query = client.collection(collection_name).where(
        filter=firestore.FieldFilter("user_id", "==", legacy_user_id)
    )
    docs = list(query.stream())
    count = 0
    for chunk_start in range(0, len(docs), 400):
        chunk = docs[chunk_start : chunk_start + 400]
        batch = client.batch()
        for doc in chunk:
            batch.update(doc.reference, {"user_id": new_uid})
        batch.commit()
        count += len(chunk)
    return count


def _rekey_profiles(client, legacy_user_id: str, new_uid: str) -> int:
    """Profiles are keyed by composite doc id f"{user_id}:{profile_id}", so
    discovery is a document-id prefix scan rather than a field filter — this
    is what finds a profile even if it has zero profile_memory entries (a gap
    in the earlier design, which discovered profiles only via profile_memory).
    Copies forward with merge=True (idempotent) and stamps the old doc rather
    than deleting it (cheap, and strictly safer than an unrecoverable delete).
    """
    collection = client.collection(settings.firestore_profile_collection)
    lower = f"{legacy_user_id}:"
    # chr(0xF8FF) is a high-codepoint sentinel (standard Firestore prefix-scan
    # idiom, spelled via chr() instead of a literal escape to keep the source
    # free of invisible characters) so the range captures every doc id that
    # starts with `lower`.
    upper = f"{legacy_user_id}:" + chr(0xF8FF)
    query = collection.where(
        filter=firestore.FieldFilter(firestore.FieldPath.document_id(), ">=", lower)
    ).where(filter=firestore.FieldFilter(firestore.FieldPath.document_id(), "<", upper))

    count = 0
    for doc in query.stream():
        data = dict(doc.to_dict() or {})
        if data.get("migrated_to") == new_uid:
            continue  # already migrated by a previous (possibly crashed) attempt
        profile_id = str(data.get("profile_id") or doc.id.split(":", 1)[-1])
        new_record = dict(data)
        new_record["user_id"] = new_uid
        new_record["profile_id"] = profile_id
        collection.document(f"{new_uid}:{profile_id}").set(new_record, merge=True)
        doc.reference.set({"migrated_to": new_uid}, merge=True)
        count += 1
    return count


def _run_migration(client, legacy_user_id: str, new_uid: str) -> dict[str, int]:
    return {
        "profiles": _rekey_profiles(client, legacy_user_id, new_uid),
        "sessions": _rekey_collection_by_field(
            client, settings.firestore_collection, legacy_user_id, new_uid
        ),
        "session_events": _rekey_collection_by_field(
            client, settings.firestore_event_collection, legacy_user_id, new_uid
        ),
        "notification_items": _rekey_collection_by_field(
            client, settings.firestore_notification_collection, legacy_user_id, new_uid
        ),
        "profile_memory": _rekey_collection_by_field(
            client, settings.firestore_profile_memory_collection, legacy_user_id, new_uid
        ),
        # push_device_tokens deliberately NOT migrated — the app re-registers
        # its FCM token under the new uid on the very next launch (the same
        # launch that triggers this migration), so copying old rows forward
        # would just create stale duplicates. Considered omission, not a gap.
    }


@router.post("/claim-legacy")
async def claim_legacy(
    payload: dict[str, object],
    uid: str = Depends(get_current_uid),
) -> dict[str, object]:
    legacy_user_id = str(payload.get("legacy_user_id") or "").strip()
    if not legacy_user_id or legacy_user_id == uid:
        raise HTTPException(
            status_code=400,
            detail="legacy_user_id is required and must differ from the caller's uid",
        )

    if not settings.firestore_enabled:
        raise HTTPException(status_code=503, detail="Firestore not enabled on this instance")

    deadline_raw = settings.legacy_claim_deadline_utc
    if not deadline_raw:
        raise HTTPException(status_code=503, detail="Legacy claim window is not configured")
    try:
        deadline_dt = datetime.fromisoformat(deadline_raw.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=503, detail="Legacy claim window is misconfigured")
    if datetime.now(timezone.utc) > deadline_dt:
        raise HTTPException(status_code=410, detail="Legacy claim window has closed")

    client = _get_client()

    outcome = await asyncio.to_thread(_acquire_or_resume_claim, client, legacy_user_id, uid)
    if outcome == "conflict":
        await asyncio.to_thread(_notify_conflict, legacy_user_id, uid)
        raise HTTPException(status_code=409, detail="This legacy id has already been claimed")
    if outcome == "already_complete":
        return {"status": "ok", "already_migrated": True}

    counts = await asyncio.to_thread(_run_migration, client, legacy_user_id, uid)
    await asyncio.to_thread(_mark_complete, client, legacy_user_id)

    return {"status": "ok", "migrated": counts}
