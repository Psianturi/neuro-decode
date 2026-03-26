"""
Moltbook Heartbeat Engine.

Runs every 30 minutes (configurable via MOLTBOOK_HEARTBEAT_INTERVAL_MINUTES).
Each cycle:
  1. GET /home — parse dashboard
  2. Reply to new comments on NeuroBuddy's own posts
  3. Browse feed — upvote + comment on relevant ASD-related posts (max 3/cycle)
  4. Possibly create a new educational post (rate: 1 per 4 cycles = ~2 hrs)
  5. Mark processed notifications as read

State is stored in a simple in-memory dict (survives per-process restart).
For multi-instance Cloud Run, promote to Firestore via state_store.py.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from app.moltbook.challenge_solver import handle_verification
from app.moltbook.moltbook_client import MoltbookClient
from app.moltbook.persona import (
    generate_comment_on_post,
    generate_post,
    generate_reply,
    is_relevant_post,
    pick_next_topic,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory state (replace with Firestore for multi-instance)
# ---------------------------------------------------------------------------

_state: dict[str, Any] = {
    "last_check_utc": None,     # ISO timestamp of last heartbeat
    "post_count": 0,            # Total posts published by this agent
    "cycle_count": 0,           # Total heartbeat cycles run
    "replied_comment_ids": set(),   # Comment IDs already replied to
    "commented_post_ids": set(),    # Post IDs already commented on
}

# How many cycles between proactive posts (1 per ~2 hours at 30-min interval)
_POST_EVERY_N_CYCLES = 4
# Max NEW comments from others we'll reply to per cycle
_MAX_REPLIES_PER_CYCLE = 3
# Max other agents' posts we'll comment on per cycle
_MAX_EXTERNAL_COMMENTS_PER_CYCLE = 2


# ---------------------------------------------------------------------------
# Core heartbeat tick
# ---------------------------------------------------------------------------


async def run_heartbeat_tick(client: MoltbookClient, model: str) -> dict:
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
        "errors": [],
    }

    logger.info("[Moltbook] Heartbeat cycle %d starting", cycle)

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
            if commenter.lower() in {"neurobuddy", "neurodecode"}:
                continue

            content: str = comment.get("content", "")
            if not content:
                continue

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
                await handle_verification(resp, model, client)
                _state["replied_comment_ids"].add(comment_id)
                replies_sent += 1
                logger.info(
                    "[Moltbook] Replied to comment %s on post %s", comment_id, post_id
                )
                # Respect comment cooldown (20s for established, 60s for new)
                await asyncio.sleep(22)
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
    # 3. Browse feed — comment on relevant external posts
    # ------------------------------------------------------------------
    external_comments = 0
    try:
        feed_resp = await client.get_feed(sort="hot", limit=25)
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
            if feed_author.lower() in {"neurobuddy", "neurodecode"}:
                continue

            # Relevance check
            try:
                relevant = await is_relevant_post(feed_title, feed_content, model)
            except Exception:
                relevant = False

            if not relevant:
                # Still upvote good posts silently
                try:
                    await client.upvote_post(feed_post_id)
                except Exception:
                    pass
                continue

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
                await handle_verification(resp, model, client)
                _state["commented_post_ids"].add(feed_post_id)
                # Also upvote
                await client.upvote_post(feed_post_id)
                external_comments += 1
                logger.info("[Moltbook] Commented on external post %s", feed_post_id)
                await asyncio.sleep(22)
            except Exception as exc:
                logger.warning("[Moltbook] External comment failed: %s", exc)
                summary["errors"].append(f"external_comment: {exc}")

    except Exception as exc:
        logger.warning("[Moltbook] Feed fetch failed: %s", exc)
        summary["errors"].append(f"feed: {exc}")

    summary["external_comments"] = external_comments

    # ------------------------------------------------------------------
    # 4. Create a proactive educational post (every N cycles)
    # ------------------------------------------------------------------
    if cycle % _POST_EVERY_N_CYCLES == 0:
        topic = pick_next_topic(_state["post_count"])
        try:
            title, body = await generate_post(topic=topic, model=model)
            resp = await client.create_post(
                submolt_name="general",
                title=title,
                content=body,
            )
            ok = await handle_verification(resp, model, client)
            if ok:
                _state["post_count"] += 1
                summary["post_created"] = True
                logger.info("[Moltbook] Post published: %s", title)
        except Exception as exc:
            logger.warning("[Moltbook] Post creation failed: %s", exc)
            summary["errors"].append(f"post: {exc}")

    logger.info(
        "[Moltbook] Cycle %d done — replies=%d ext_comments=%d post=%s errors=%d",
        cycle,
        summary["replies_sent"],
        summary["external_comments"],
        summary["post_created"],
        len(summary["errors"]),
    )
    return summary


def get_state_snapshot() -> dict:
    """Return a JSON-safe snapshot of heartbeat state for the debug endpoint."""
    return {
        "last_check_utc": _state["last_check_utc"],
        "post_count": _state["post_count"],
        "cycle_count": _state["cycle_count"],
        "replied_comment_ids_count": len(_state["replied_comment_ids"]),
        "commented_post_ids_count": len(_state["commented_post_ids"]),
    }
