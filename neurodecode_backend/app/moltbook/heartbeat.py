"""
Moltbook Heartbeat Engine.

Runs every 30 minutes (configurable via MOLTBOOK_HEARTBEAT_INTERVAL_MINUTES).
Each cycle:
  1. GET /home — parse dashboard
  2. Reply to new comments on NeuroBuddy's own posts
  3. Browse feed — upvote + comment on relevant posts (max 1/cycle)
  4. Possibly create a new educational post (rate: ~2–3 per day = every 8 hrs)
  5. Mark processed notifications as read

State is stored in a simple in-memory dict (survives per-process restart).
For multi-instance Cloud Run, promote to Firestore via state_store.py.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.moltbook.challenge_solver import handle_verification
from app.moltbook.moltbook_client import MoltbookClient
from app.moltbook.persona import (
    generate_comment_on_post,
    generate_dm_reply,
    generate_introduction,
    generate_post,
    generate_reply,
    is_relevant_post,
    pick_next_topic,
)
from app.moltbook.agents.orchestrator import AgentOrchestrator, PipelineContext
from app.moltbook.dedup_store import flush_dedup_state, load_dedup_state

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory state (replace with Firestore for multi-instance)
# ---------------------------------------------------------------------------

_state: dict[str, Any] = {
    "last_check_utc": None,     # ISO timestamp of last heartbeat
    "last_post_utc": None,      # ISO timestamp of last published post
    "post_count": 0,            # Total posts published by this agent
    "cycle_count": 0,           # Total heartbeat cycles run
    "replied_comment_ids": set(),   # Comment IDs already replied to
    "commented_post_ids": set(),    # Post IDs already commented on
    "comments_today": 0,        # Comments sent today (resets at UTC midnight)
    "comments_today_date": None,    # UTC date string for today's counter
    "intro_posted": False,      # Whether introduction post in m/introductions was done
    "subscribed": False,        # Whether submolt subscriptions were done
    "dm_request_ids_notified": set(),   # DM request IDs already logged (pending approval)
    "upvotes_by_author": {},            # author_name -> upvote count (for follow logic)
    "followed_agents": set(),           # agent names we've already followed
    "upvoted_comment_ids": set(),       # comment IDs already upvoted
    "upvoted_post_ids": set(),           # post IDs already upvoted
    "last_pipeline_result": None,        # last pipeline summary for /pipeline/last endpoint
    "dedup_loaded": False,               # whether Firestore dedup state has been loaded
}

# Submolts to subscribe to on first run
_SUBMOLTS_TO_SUBSCRIBE = [
    "general", "introductions", "philosophy", "todayilearned", "ai",
    "blesstheirhearts", "emergence", "ponderings",
]

# Minimum hours between proactive posts (API-guarded to survive cold start)
_POST_INTERVAL_HOURS = 5.5
# Moltbook rule: max 50 comments/day (established agent). 
_MAX_COMMENTS_PER_DAY = 32
# Max NEW comments from others we'll reply to per cycle
_MAX_REPLIES_PER_CYCLE = 2
# Max other agents' posts we'll comment on per cycle
_MAX_EXTERNAL_COMMENTS_PER_CYCLE = 2
# Moltbook rule: min 20s between comments (established). We use 30s for safety.
_COMMENT_COOLDOWN_SECONDS = 30
# Follow a molty once we've upvoted this many of their posts
_FOLLOW_UPVOTE_THRESHOLD = 3


# ---------------------------------------------------------------------------
# Daily comment counter (resets at UTC midnight)
# ---------------------------------------------------------------------------


def _can_comment() -> bool:
    """Check daily comment budget. Returns False if limit reached."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if _state["comments_today_date"] != today:
        _state["comments_today"] = 0
        _state["comments_today_date"] = today
    return _state["comments_today"] < _MAX_COMMENTS_PER_DAY


def _record_comment() -> None:
    """Increment daily comment counter."""
    _state["comments_today"] += 1


# ---------------------------------------------------------------------------
# Follow helper
# ---------------------------------------------------------------------------


async def _check_follow(author: str, client: MoltbookClient) -> None:
    """Follow a molty once we've upvoted _FOLLOW_UPVOTE_THRESHOLD of their posts."""
    if not author or author.lower() in {"anakunggul", "neurobuddy", "neurodecode"}:
        return
    if author in _state["followed_agents"]:
        return
    _state["upvotes_by_author"][author] = _state["upvotes_by_author"].get(author, 0) + 1
    if _state["upvotes_by_author"][author] >= _FOLLOW_UPVOTE_THRESHOLD:
        try:
            await client.follow(author)
            _state["followed_agents"].add(author)
            logger.info("[Moltbook] Followed %s after %d upvotes", author, _FOLLOW_UPVOTE_THRESHOLD)
        except Exception as exc:
            logger.warning("[Moltbook] Follow %s failed: %s", author, exc)


# ---------------------------------------------------------------------------
# DM check (HEARTBEAT Step 3)
# ---------------------------------------------------------------------------


async def _run_dm_check(home: dict, client: MoltbookClient, model: str) -> None:
    """
    Handle DM activity per MESSAGING.md and HEARTBEAT Step 3.
    - Pending requests: log only — human must approve via dashboard.
    - Unread messages in approved convos: auto-reply with Gemini.
    """
    dm_data = home.get("your_direct_messages", {})
    pending_count = dm_data.get("pending_request_count", 0)
    unread_count = dm_data.get("unread_message_count", 0)

    if not pending_count and not unread_count:
        return

    # Pending requests: log only — human must approve
    if pending_count:
        try:
            reqs_resp = await client.dm_requests()
            items = reqs_resp.get("requests", {}).get("items", [])
            for req in items:
                req_id = req.get("conversation_id", "")
                if req_id and req_id not in _state["dm_request_ids_notified"]:
                    from_name = req.get("from", {}).get("name", "unknown")
                    preview = req.get("message_preview", "")[:80]
                    logger.info(
                        "[Moltbook] DM request from %s (id=%s): %s — human must approve",
                        from_name, req_id, preview,
                    )
                    _state["dm_request_ids_notified"].add(req_id)
        except Exception as exc:
            logger.warning("[Moltbook] DM requests fetch failed: %s", exc)

    # Unread messages in approved conversations: auto-reply
    if unread_count:
        try:
            convos_resp = await client.dm_conversations()
            items = convos_resp.get("conversations", {}).get("items", [])
            for convo in items:
                if convo.get("unread_count", 0) <= 0:
                    continue
                convo_id = convo.get("conversation_id", "")
                if not convo_id:
                    continue
                try:
                    detail = await client.dm_read_conversation(convo_id)
                    messages = detail.get("messages", [])
                    if not messages:
                        continue
                    other_msgs = [
                        m for m in messages
                        if m.get("sender", {}).get("name", "").lower()
                        not in {"anakunggul", "neurobuddy", "neurodecode"}
                    ]
                    if not other_msgs:
                        continue
                    last = other_msgs[-1]
                    if last.get("needs_human_input"):
                        logger.info(
                            "[Moltbook] DM from %s needs human input — skipping auto-reply",
                            last.get("sender", {}).get("name", "?"),
                        )
                        continue
                    sender = last.get("sender", {}).get("name", "unknown")
                    content = last.get("content", "")
                    reply = await generate_dm_reply(
                        sender_name=sender,
                        message_content=content,
                        model=model,
                    )
                    await client.dm_send_message(convo_id, reply)
                    logger.info("[Moltbook] Replied to DM from %s in convo %s", sender, convo_id)
                except Exception as exc:
                    logger.warning("[Moltbook] DM convo %s failed: %s", convo_id, exc)
        except Exception as exc:
            logger.warning("[Moltbook] DM conversations fetch failed: %s", exc)


# ---------------------------------------------------------------------------
# One-time onboarding (runs once per process lifetime after first heartbeat)
# ---------------------------------------------------------------------------


async def _run_onboarding(client: MoltbookClient, model: str) -> None:
    """
    Subscribe to relevant submolts and post introduction to m/introductions.
    Runs once per process; state flags prevent re-runs on same container.
    """
    # Step 1: Subscribe to submolts
    if not _state["subscribed"]:
        success_count = 0
        for submolt in _SUBMOLTS_TO_SUBSCRIBE:
            try:
                await client.subscribe_submolt(submolt)
                logger.info("[Moltbook] Subscribed to m/%s", submolt)
                success_count += 1
            except Exception as exc:
                logger.warning("[Moltbook] Subscribe m/%s failed: %s", submolt, exc)
        if success_count > 0:
            _state["subscribed"] = True
            logger.warning("[Moltbook] Subscribed to %d/%d submolts", success_count, len(_SUBMOLTS_TO_SUBSCRIBE))
        else:
            logger.warning("[Moltbook] All submolt subscribes failed — will retry next cycle")

    # Step 2: Post introduction to m/introductions (only once ever)
    if not _state["intro_posted"]:
        # Check via API first — survives cold start / state reset
        already_introduced = False
        try:
            profile = await client.get_agent_profile("anakunggul")
            recent_posts = profile.get("recentPosts", [])
            already_introduced = any(
                p.get("submolt_name") == "introductions" or
                p.get("submolt", {}).get("name") == "introductions"
                for p in recent_posts
            )
        except Exception as exc:
            logger.warning("[Moltbook] Could not check profile for intro guard: %s", exc)

        if already_introduced:
            _state["intro_posted"] = True
            logger.info("[Moltbook] Introduction already exists — skipping")
        else:
            try:
                title, body = await generate_introduction(model=model)
                resp = await client.create_post(
                    submolt_name="introductions",
                    title=title,
                    content=body,
                )
                ok = await handle_verification(resp, model, client)
                if ok:
                    _state["intro_posted"] = True
                    _state["last_post_utc"] = datetime.now(timezone.utc).isoformat()
                    logger.info("[Moltbook] Introduction posted to m/introductions: %s", title)
                else:
                    logger.warning("[Moltbook] Introduction verification failed")
            except Exception as exc:
                logger.warning("[Moltbook] Introduction post failed: %s", exc)


# ---------------------------------------------------------------------------
# Core heartbeat tick
# ---------------------------------------------------------------------------


async def run_heartbeat_tick(
    client: MoltbookClient,
    model: str,
    orchestrator: AgentOrchestrator | None = None,
    firestore_project: str | None = None,
) -> dict:
    """
    Execute one heartbeat cycle. Returns a summary dict for logging.
    """
    cycle = _state["cycle_count"] + 1
    _state["cycle_count"] = cycle
    _state["last_check_utc"] = datetime.now(timezone.utc).isoformat()

    summary: dict[str, Any] = {
        "cycle": cycle,
        "replies_sent": 0,
        "external_comments": 0,
        "post_created": False,
        "hours_since_last_post": None,
        "errors": [],
    }

    logger.info("[Moltbook] Heartbeat cycle %d starting", cycle)

    # ------------------------------------------------------------------
    # 0b. Load dedup state from Firestore (once per process lifetime)
    # ------------------------------------------------------------------
    if firestore_project and not _state["dedup_loaded"]:
        await load_dedup_state(firestore_project, _state)
        _state["dedup_loaded"] = True
        # WAL: flush immediately after load so Firestore reflects current state
        # before any actions are taken — prevents duplicate actions if cycle crashes
        await flush_dedup_state(firestore_project, _state)

    # ------------------------------------------------------------------
    # 0a. Run multi-agent context pipeline (non-blocking on failure)
    # ------------------------------------------------------------------
    pipeline_ctx: PipelineContext | None = None
    if orchestrator is not None:
        try:
            pipeline_ctx = await orchestrator.run_context_pipeline(
                moltbook_client=client,
            )
            if pipeline_ctx.errors:
                logger.warning("[Moltbook] Pipeline errors: %s", pipeline_ctx.errors)
        except Exception as exc:
            logger.warning("[Moltbook] Agent pipeline failed: %s", exc)
            pipeline_ctx = None

    # Store pipeline result for debug endpoint (always, even if no insight)
    if pipeline_ctx is not None:
        _state["last_pipeline_result"] = {
            "cycle": cycle,
            "timestamp_utc": _state["last_check_utc"],
            "has_session_data": pipeline_ctx.session_ctx.has_data,
            "session_count": pipeline_ctx.session_ctx.session_count,
            "insight_topic": pipeline_ctx.insight.topic if pipeline_ctx.insight else None,
            "insight_angle": pipeline_ctx.insight.angle if pipeline_ctx.insight else None,
            "persona": pipeline_ctx.insight.persona_key if pipeline_ctx.insight else None,
            "suggested_submolt": pipeline_ctx.insight.suggested_submolt if pipeline_ctx.insight else None,
            "pipeline_errors": pipeline_ctx.errors,
        }

    # ------------------------------------------------------------------
    # 0. One-time onboarding: subscribe to submolts + post introduction
    # ------------------------------------------------------------------
    if not _state["subscribed"] or not _state["intro_posted"]:
        await _run_onboarding(client, model)

    # ------------------------------------------------------------------
    # 1. GET /home — check notifications & activity on own posts
    # ------------------------------------------------------------------
    try:
        home = await client.home()
    except Exception as exc:
        logger.error("[Moltbook] /home failed: %s", exc)
        summary["errors"].append(f"home: {exc}")
        return summary

    activity_on_posts: list[dict] = home.get("activity_on_your_posts", [])

    # ------------------------------------------------------------------
    # 2. Reply to new comments on NeuroBuddy's own posts
    # ------------------------------------------------------------------
    replies_sent = 0
    for post_activity in activity_on_posts:
        if replies_sent >= _MAX_REPLIES_PER_CYCLE:
            break
        post_id: str = post_activity.get("post_id", "")
        post_title: str = post_activity.get("post_title", "")
        if not post_id:
            continue

        try:
            comments_resp = await client.get_comments(post_id, sort="new", limit=10)
            comments: list[dict] = comments_resp.get("comments", [])
        except Exception as exc:
            logger.warning("[Moltbook] Failed to fetch comments for %s: %s", post_id, exc)
            continue

        for comment in comments:
            if replies_sent >= _MAX_REPLIES_PER_CYCLE:
                break
            comment_id: str = comment.get("id", "")
            if not comment_id or comment_id in _state["replied_comment_ids"]:
                continue
            # Don't reply to self
            commenter: str = comment.get("author", {}).get("name", "")
            if commenter.lower() in {"anakunggul", "neurobuddy", "neurodecode"}:
                continue

            # Upvote the comment (builds community, helps the author)
            if comment_id not in _state["upvoted_comment_ids"]:
                try:
                    await client.upvote_comment(comment_id)
                    _state["upvoted_comment_ids"].add(comment_id)
                except Exception:
                    pass

            content: str = comment.get("content", "")
            if not content:
                continue
            if not _can_comment():
                logger.info("[Moltbook] Daily comment budget reached, skipping replies")
                break

            try:
                reply_text = await generate_reply(
                    original_post_title=post_title,
                    comment_content=content,
                    commenter_name=commenter,
                    model=model,
                )
                resp = await client.add_comment(
                    post_id=post_id,
                    content=reply_text,
                    parent_id=comment_id,
                )
                ok = await handle_verification(resp, model, client)
                if ok:
                    _state["replied_comment_ids"].add(comment_id)
                    _record_comment()
                    replies_sent += 1
                    logger.info(
                        "[Moltbook] Replied to comment %s on post %s", comment_id, post_id
                    )
                else:
                    logger.warning(
                        "[Moltbook] Reply verification failed for comment %s", comment_id
                    )
                await asyncio.sleep(_COMMENT_COOLDOWN_SECONDS)
            except Exception as exc:
                logger.warning("[Moltbook] Reply failed: %s", exc)
                summary["errors"].append(f"reply: {exc}")

        # Mark notifications read for this post
        try:
            await client.read_notifications_by_post(post_id)
        except Exception:
            pass

    summary["replies_sent"] = replies_sent

    # ------------------------------------------------------------------
    # DM Check (HEARTBEAT) — log pending, reply to unread
    # ------------------------------------------------------------------
    await _run_dm_check(home, client, model)

    # ------------------------------------------------------------------
    # 3. Browse feed — comment on relevant external posts
    # ------------------------------------------------------------------
    external_comments = 0
    try:
        feed_resp = await client.get_feed(sort="hot", limit=12)
        feed_posts: list[dict] = feed_resp.get("posts", [])

        for feed_post in feed_posts:
            if external_comments >= _MAX_EXTERNAL_COMMENTS_PER_CYCLE:
                break
            feed_post_id: str = feed_post.get("post_id") or feed_post.get("id", "")
            if not feed_post_id or feed_post_id in _state["commented_post_ids"]:
                continue

            feed_title: str = feed_post.get("title", "")
            feed_content: str = feed_post.get("content_preview") or feed_post.get("content", "")
            feed_author: str = feed_post.get("author_name") or feed_post.get("author", {}).get("name", "")

            # Skip if same author
            if feed_author.lower() in {"anakunggul", "neurobuddy", "neurodecode"}:
                continue

            # Relevance check
            try:
                relevant = await is_relevant_post(feed_title, feed_content, model)
            except Exception:
                relevant = False

            if not relevant:
                # Still upvote good posts silently
                if feed_post_id not in _state["upvoted_post_ids"]:
                    try:
                        await client.upvote_post(feed_post_id)
                        _state["upvoted_post_ids"].add(feed_post_id)
                        await _check_follow(feed_author, client)
                    except Exception:
                        pass
                continue

            if not _can_comment():
                logger.info("[Moltbook] Daily comment budget reached, skipping external comments")
                break

            # Comment on the relevant post
            try:
                comment_text = await generate_comment_on_post(
                    post_title=feed_title,
                    post_content=feed_content,
                    author_name=feed_author,
                    model=model,
                )
                resp = await client.add_comment(
                    post_id=feed_post_id,
                    content=comment_text,
                )
                ok = await handle_verification(resp, model, client)
                if ok:
                    _state["commented_post_ids"].add(feed_post_id)
                    _state["upvoted_post_ids"].add(feed_post_id)
                    _record_comment()
                    await client.upvote_post(feed_post_id)
                    await _check_follow(feed_author, client)
                    external_comments += 1
                    logger.info("[Moltbook] Commented on external post %s", feed_post_id)
                else:
                    logger.warning(
                        "[Moltbook] External comment verification failed for post %s — resp: %s",
                        feed_post_id, resp
                    )
                await asyncio.sleep(_COMMENT_COOLDOWN_SECONDS)
            except Exception as exc:
                logger.warning("[Moltbook] External comment failed: %s", exc)
                summary["errors"].append(f"external_comment: {exc}")

    except Exception as exc:
        logger.warning("[Moltbook] Feed fetch failed: %s", exc)
        summary["errors"].append(f"feed: {exc}")

    summary["external_comments"] = external_comments

    # ------------------------------------------------------------------
    # 4. Create a proactive educational post (API-guarded, cold-start safe)
    # ------------------------------------------------------------------
    now_utc = datetime.now(timezone.utc)

    # Determine hours since last post via Moltbook API first.
    # This survives cold starts where last_post_utc is always None.
    hours_since_post: float = 0.0
    try:
        profile = await client.get_agent_profile("anakunggul")
        recent = profile.get("recentPosts", [])
        if recent:
            latest_ts = max(
                (p.get("created_at") or p.get("createdAt") or "") for p in recent
            )
            if latest_ts:
                last_dt = datetime.fromisoformat(latest_ts.replace("Z", "+00:00"))
                hours_since_post = (now_utc - last_dt).total_seconds() / 3600
                _state["last_post_utc"] = last_dt.isoformat()
    except Exception as exc:
        logger.warning("[Moltbook] Could not fetch profile for post timing: %s", exc)
        # Fallback to in-memory; cold start with no info → conservative skip
        last_post_mem = _state.get("last_post_utc")
        if last_post_mem:
            hours_since_post = (
                now_utc - datetime.fromisoformat(last_post_mem)
            ).total_seconds() / 3600
        # else: hours_since_post stays 0.0 → skip post this cycle

    if hours_since_post >= _POST_INTERVAL_HOURS:
        # Use insight from pipeline if available, else fall back to topic rotation
        if pipeline_ctx is not None and pipeline_ctx.insight is not None:
            topic = pipeline_ctx.insight.topic
            submolt = pipeline_ctx.insight.suggested_submolt
        else:
            topic = pick_next_topic(_state["post_count"])
            submolt = "general"
        try:
            title, body = await generate_post(
                topic=topic,
                model=model,
                insight=pipeline_ctx.insight if pipeline_ctx else None,
                persona_system_addendum=pipeline_ctx.persona_system_addendum if pipeline_ctx else "",
            )
            # ReviewAgent quality gate
            if orchestrator is not None and pipeline_ctx is not None:
                verdict = await orchestrator.review_draft(
                    pipeline_ctx=pipeline_ctx,
                    title=title,
                    body=body,
                    submolt=submolt,
                )
                if not verdict.approved:
                    logger.warning("[Moltbook] Post rejected by ReviewAgent: %s", verdict.reason)
                    summary["errors"].append(f"review_rejected: {verdict.reason}")
                    if _state["last_pipeline_result"] is not None:
                        _state["last_pipeline_result"]["post_published"] = False
                        _state["last_pipeline_result"]["post_title"] = title
                        _state["last_pipeline_result"]["review_verdict"] = "rejected"
                        _state["last_pipeline_result"]["review_reason"] = verdict.reason
                    summary["hours_since_last_post"] = round(hours_since_post, 1)
                    return summary
                # Apply reviewer revisions if any
                if verdict.revised_title:
                    title = verdict.revised_title
                if verdict.revised_body:
                    body = verdict.revised_body

            resp = await client.create_post(
                submolt_name=submolt,
                title=title,
                content=body,
            )
            ok = await handle_verification(resp, model, client)
            if ok:
                _state["post_count"] += 1
                _state["last_post_utc"] = now_utc.isoformat()
                summary["post_created"] = True
                summary["post_title"] = title
                summary["post_topic"] = topic
                summary["post_submolt"] = submolt
                # Update pipeline result with publish outcome
                if _state["last_pipeline_result"] is not None:
                    _state["last_pipeline_result"]["post_published"] = True
                    _state["last_pipeline_result"]["post_title"] = title
                    _state["last_pipeline_result"]["review_verdict"] = "approved"
                logger.info("[Moltbook] Post published: %s", title)
            else:
                logger.warning("[Moltbook] Post verification failed: %s", resp)
        except Exception as exc:
            logger.warning("[Moltbook] Post creation failed: %s", exc)
            summary["errors"].append(f"post: {exc}")
    else:
        logger.info(
            "[Moltbook] Skipping post — %.1fh since last (need %.1fh)",
            hours_since_post, _POST_INTERVAL_HOURS,
        )

    summary["hours_since_last_post"] = round(hours_since_post, 1)
    logger.info(
        "[Moltbook] Cycle %d done — replies=%d ext_comments=%d post=%s errors=%d",
        cycle,
        summary["replies_sent"],
        summary["external_comments"],
        summary["post_created"],
        len(summary["errors"]),
    )

    # ------------------------------------------------------------------
    # 5. Flush dedup sets to Firestore (best-effort, non-blocking on fail)
    # ------------------------------------------------------------------
    if firestore_project:
        await flush_dedup_state(firestore_project, _state)

    return summary


def get_state_snapshot() -> dict:
    """Return a JSON-safe snapshot of heartbeat state for the debug endpoint."""
    return {
        "last_check_utc": _state["last_check_utc"],
        "post_count": _state["post_count"],
        "cycle_count": _state["cycle_count"],
        "last_post_utc": _state.get("last_post_utc"),
        "intro_posted": _state["intro_posted"],
        "subscribed": _state["subscribed"],
        "comments_today": _state["comments_today"],
        "comments_today_budget": _MAX_COMMENTS_PER_DAY,
        "replied_comment_ids_count": len(_state["replied_comment_ids"]),
        "commented_post_ids_count": len(_state["commented_post_ids"]),
        "followed_agents_count": len(_state["followed_agents"]),
        "upvoted_comment_ids_count": len(_state["upvoted_comment_ids"]),
        "upvoted_post_ids_count": len(_state["upvoted_post_ids"]),
        "dm_requests_notified_count": len(_state["dm_request_ids_notified"]),
    }


def get_last_pipeline_result() -> dict | None:
    """Return the last pipeline result for the debug endpoint."""
    return _state.get("last_pipeline_result")


def increment_post_count() -> None:
    """Increment post_count after a manual post succeeds (called by router)."""
    _state["post_count"] += 1
