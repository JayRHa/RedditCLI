"""Tests for transformation helpers."""

from __future__ import annotations

from reddit_cli.transform import (
    to_utc_iso,
    transform_post,
    transform_posts,
    transform_subreddit_info,
)


def test_to_utc_iso() -> None:
    assert to_utc_iso(1700000000) == "2023-11-14T22:13:20+00:00"
    assert to_utc_iso(None) is None


def test_transform_post() -> None:
    raw = {
        "id": "abc123",
        "title": "Test Post Title",
        "author": "testuser",
        "subreddit": "python",
        "score": 42,
        "upvote_ratio": 0.95,
        "num_comments": 7,
        "url": "https://example.com/article",
        "permalink": "/r/python/comments/abc123/test_post_title/",
        "selftext": "This is the body text.",
        "created_utc": 1700000000,
        "is_self": False,
        "over_18": False,
        "link_flair_text": "Discussion",
    }

    result = transform_post(raw)

    assert result["id"] == "abc123"
    assert result["title"] == "Test Post Title"
    assert result["author"] == "testuser"
    assert result["score"] == 42
    assert result["num_comments"] == 7
    assert result["selftext"] == "This is the body text."
    assert result["created_utc"] == "2023-11-14T22:13:20+00:00"
    assert result["is_self"] is False
    assert result["link_flair_text"] == "Discussion"


def test_transform_post_missing_fields() -> None:
    raw: dict = {}
    result = transform_post(raw)

    assert result["id"] is None
    assert result["title"] is None
    assert result["score"] is None
    assert result["selftext"] is None
    assert result["created_utc"] is None


def test_transform_post_empty_selftext() -> None:
    raw = {"selftext": ""}
    result = transform_post(raw)
    assert result["selftext"] is None


def test_transform_posts() -> None:
    listing = {
        "data": {
            "children": [
                {
                    "kind": "t3",
                    "data": {
                        "id": "post1",
                        "title": "First Post",
                        "author": "user1",
                        "subreddit": "python",
                        "score": 100,
                        "upvote_ratio": 0.98,
                        "num_comments": 15,
                        "url": "https://example.com",
                        "permalink": "/r/python/comments/post1/first_post/",
                        "selftext": "",
                        "created_utc": 1700000000,
                        "is_self": False,
                        "over_18": False,
                        "link_flair_text": None,
                    },
                },
                {
                    "kind": "t3",
                    "data": {
                        "id": "post2",
                        "title": "Second Post",
                        "author": "user2",
                        "subreddit": "python",
                        "score": 50,
                        "upvote_ratio": 0.90,
                        "num_comments": 3,
                        "url": "https://self.reddit.com",
                        "permalink": "/r/python/comments/post2/second_post/",
                        "selftext": "Some self text here",
                        "created_utc": 1700003600,
                        "is_self": True,
                        "over_18": False,
                        "link_flair_text": "Help",
                    },
                },
            ]
        }
    }

    result = transform_posts(listing)

    assert len(result) == 2
    assert result[0]["id"] == "post1"
    assert result[0]["title"] == "First Post"
    assert result[0]["selftext"] is None  # empty string -> None
    assert result[1]["id"] == "post2"
    assert result[1]["selftext"] == "Some self text here"


def test_transform_posts_empty_listing() -> None:
    result = transform_posts({"data": {"children": []}})
    assert result == []


def test_transform_posts_missing_data() -> None:
    result = transform_posts({})
    assert result == []


def test_transform_subreddit_info() -> None:
    raw = {
        "kind": "t5",
        "data": {
            "display_name": "python",
            "title": "Python",
            "public_description": "News about the Python programming language.",
            "description": "Full description with markdown...",
            "subscribers": 1200000,
            "accounts_active": 5000,
            "created_utc": 1137459600,
            "over18": False,
            "subreddit_type": "public",
            "url": "/r/python/",
        },
    }

    result = transform_subreddit_info(raw)

    assert result["name"] == "python"
    assert result["title"] == "Python"
    assert result["subscribers"] == 1200000
    assert result["active_users"] == 5000
    assert result["over_18"] is False
    assert result["subreddit_type"] == "public"
    assert result["created_utc"] is not None


def test_transform_subreddit_info_missing_fields() -> None:
    raw = {"data": {}}
    result = transform_subreddit_info(raw)

    assert result["name"] is None
    assert result["subscribers"] is None
    assert result["public_description"] is None
    assert result["description"] is None
