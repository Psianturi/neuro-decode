from __future__ import annotations

"""
Time-Delayed Proactive Follow-up Engine

After a high-severity session, a followup_scheduled_at timestamp is written
to the session document. This engine scans for due follow-ups and delivers
FCM + optional Telegram check-in notifications to the caregiver.

Entry point: POST /sessions/process-followups
Called by Cloud Scheduler every 15 minutes.
"""

import asyncio
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_FOLLOWUP_FCM_TITLE = "How is everything now?"
_FOLLOWUP_FCM_BODY = (
    "We noticed an intense session earlier. Checking in — how is your child doing now? "
    "Tap to review recovery guidance."
)
_FOLLOWUP_TELEGRAM_TEMPLATE = (
    "⏰ *NeuroDecode Follow\\-Up Check\\-In*\n"
    "Session `{session_id}` had a high\\-severity pattern\\.\n"
    "Scheduled check\\-in delivered to caregiver at {sent_at}\\."
)


async def process_pending_followups(
    *,
    session_store,
    push_device_store,
    push_sender,
    telegram_bot_token: str | None = None,
    telegram_chat_id: str | None = None,
    fcm_enabled: bool = False,
) -> dict[str, object]:
    """
    Scan Firestore for sessions with due follow-ups and deliver FCM notifications.
    Returns a summary dict: {scanned, delivered, skipped, errors}.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    pending = await session_store.scan_pending_followups(now_iso)

    delivered = 0
    skipped = 0
    errors = 0

    for doc_id, record in pending:
        session_id = str(record.get("session_id") or doc_id)
        user_id = str(record.get("user_id") or "").strip() or None
        profile_id = str(record.get("profile_id") or "").strip() or None

        if not user_id:
            logger.warning("[followup] session_id=%s missing user_id — skip", session_id)
            skipped += 1
            continue

        # Atomic mark-sent first — prevents double delivery across instances
        sent_at = datetime.now(timezone.utc).isoformat()
        marked = await session_store.mark_followup_sent(doc_id, sent_at)
        if not marked:
            logger.info("[followup] session_id=%s already sent — skip", session_id)
            skipped += 1
            continue

        # Deliver FCM
        try:
            if fcm_enabled:
                tokens = await push_device_store.list_active_tokens(
                    user_id=user_id,
                    profile_id=profile_id,
                )
                if not tokens and profile_id:
                    tokens = await push_device_store.list_active_tokens(
                        user_id=user_id,
                        profile_id=None,
                    )

                if tokens:
                    result = await push_sender.send_to_tokens(
                        tokens=tokens,
                        title=_FOLLOWUP_FCM_TITLE,
                        body=_FOLLOWUP_FCM_BODY,
                        data={
                            "type": "followup_checkin",
                            "session_id": session_id,
                            "profile_id": profile_id or "",
                        },
                    )
                    success = int(result.get("success_count") or 0)
                    logger.warning(
                        "[followup] Delivered FCM session_id=%s user_id=%s tokens=%d success=%d",
                        session_id, user_id, len(tokens), success,
                    )
                    delivered += 1
                else:
                    logger.warning(
                        "[followup] No active tokens for user_id=%s — marking sent anyway",
                        user_id,
                    )
                    skipped += 1

            # Telegram (dev monitoring channel)
            if telegram_bot_token and telegram_chat_id:
                from urllib import parse as urlparse, request as urlrequest
                text = _FOLLOWUP_TELEGRAM_TEMPLATE.format(
                    session_id=session_id,
                    sent_at=sent_at.replace("-", "\\-").replace(":", "\\:").replace(".", "\\."),
                )
                payload = {
                    "chat_id": str(telegram_chat_id).strip(),
                    "text": text,
                    "parse_mode": "MarkdownV2",
                    "disable_web_page_preview": "true",
                }
                encoded = urlparse.urlencode(payload).encode("utf-8")
                req = urlrequest.Request(
                    f"https://api.telegram.org/bot{str(telegram_bot_token).strip()}/sendMessage",
                    data=encoded,
                    method="POST",
                )
                req.add_header("Content-Type", "application/x-www-form-urlencoded")
                try:
                    await asyncio.to_thread(urlrequest.urlopen, req, timeout=10)
                except Exception as tg_err:
                    logger.warning("[followup] Telegram delivery failed: %s", tg_err)

        except Exception as exc:
            logger.warning("[followup] Delivery error session_id=%s: %s", session_id, exc)
            errors += 1

    logger.warning(
        "[followup] Scan complete — pending=%d delivered=%d skipped=%d errors=%d",
        len(pending), delivered, skipped, errors,
    )
    return {
        "scanned": len(pending),
        "delivered": delivered,
        "skipped": skipped,
        "errors": errors,
        "processed_at_utc": now_iso,
    }
