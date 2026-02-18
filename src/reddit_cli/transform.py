"""Transform raw Reddit API responses into normalized CLI payloads."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any


def _dig(data: Mapping[str, Any], *path: str, default: Any = None) -> Any:
    """Read nested dict fields safely."""
    current: Any = data
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            return default
        current = current[key]
    return current


def to_utc_iso(epoch: int | float | None) -> str | None:
    """Convert epoch timestamp to UTC ISO8601 string."""
    if epoch is None:
        return None
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def transform_post(data: Mapping[str, Any]) -> dict[str, Any]:
    """Transform a single Reddit post into a normalized dict."""
    return {
        "id": data.get("id"),
        "title": data.get("title"),
        "author": data.get("author"),
        "subreddit": data.get("subreddit"),
        "score": data.get("score"),
        "upvote_ratio": data.get("upvote_ratio"),
        "num_comments": data.get("num_comments"),
        "url": data.get("url"),
        "permalink": data.get("permalink"),
        "selftext": data.get("selftext") or None,
        "created_utc": to_utc_iso(data.get("created_utc")),
        "is_self": data.get("is_self"),
        "over_18": data.get("over_18"),
        "link_flair_text": data.get("link_flair_text"),
    }


def transform_posts(listing: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Transform a Reddit listing response into a list of normalized posts."""
    children = _dig(listing, "data", "children", default=[])
    return [transform_post(child.get("data", {})) for child in children]


def transform_subreddit_info(data: Mapping[str, Any]) -> dict[str, Any]:
    """Transform subreddit about response into normalized dict."""
    sub = _dig(data, "data", default=data)
    return {
        "name": sub.get("display_name"),
        "title": sub.get("title"),
        "public_description": sub.get("public_description") or None,
        "description": sub.get("description") or None,
        "subscribers": sub.get("subscribers"),
        "active_users": sub.get("accounts_active"),
        "created_utc": to_utc_iso(sub.get("created_utc")),
        "over_18": sub.get("over18"),
        "subreddit_type": sub.get("subreddit_type"),
        "url": sub.get("url"),
    }
