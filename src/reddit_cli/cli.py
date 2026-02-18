"""Command line interface for Reddit."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Sequence
from typing import Any

from aiohttp import BasicAuth, ClientError, ClientSession, ClientTimeout

from .const import (
    API_BASE_URL,
    DEFAULT_LIMIT,
    LISTING_COMMANDS,
    MAX_LIMIT,
    TOKEN_URL,
    USER_AGENT,
    VALID_SORT_OPTIONS,
    VALID_TIME_FILTERS,
)
from .transform import transform_posts, transform_subreddit_info


class CliInputError(ValueError):
    """Raised for invalid CLI argument combinations."""


class RedditAuthError(Exception):
    """Raised when Reddit returns an authentication error."""


class RedditApiError(Exception):
    """Raised when Reddit returns an API error."""


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="reddit",
        description="High-signal CLI for Reddit posts, subreddit info and search",
    )
    parser.add_argument(
        "--client-id",
        default=os.getenv("REDDIT_CLIENT_ID"),
        help="Reddit app client ID (or env REDDIT_CLIENT_ID)",
    )
    parser.add_argument(
        "--client-secret",
        default=os.getenv("REDDIT_CLIENT_SECRET"),
        help="Reddit app client secret (or env REDDIT_CLIENT_SECRET)",
    )
    parser.add_argument(
        "--json", dest="json_output", action="store_true", help="Output as JSON"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # hot / new / rising share the same flags
    for cmd, help_text in [
        ("hot", "Get hot posts from a subreddit"),
        ("new", "Get new posts from a subreddit"),
        ("rising", "Get rising posts from a subreddit"),
    ]:
        sub = subparsers.add_parser(cmd, help=help_text)
        sub.add_argument("--subreddit", "-s", required=True, help="Subreddit name")
        sub.add_argument(
            "--limit", "-l", type=int, default=DEFAULT_LIMIT, help="Number of posts"
        )

    # top has an extra --time flag
    top_parser = subparsers.add_parser("top", help="Get top posts from a subreddit")
    top_parser.add_argument("--subreddit", "-s", required=True, help="Subreddit name")
    top_parser.add_argument(
        "--limit", "-l", type=int, default=DEFAULT_LIMIT, help="Number of posts"
    )
    top_parser.add_argument(
        "--time",
        "-t",
        default="day",
        help="Time filter: hour, day, week, month, year, all",
    )

    # search
    search_parser = subparsers.add_parser("search", help="Search Reddit posts")
    search_parser.add_argument("--query", "-q", required=True, help="Search query")
    search_parser.add_argument("--subreddit", "-s", help="Limit search to subreddit")
    search_parser.add_argument(
        "--limit", "-l", type=int, default=DEFAULT_LIMIT, help="Number of results"
    )
    search_parser.add_argument(
        "--sort", default="relevance", help="Sort: relevance, hot, top, new, comments"
    )
    search_parser.add_argument(
        "--time",
        "-t",
        default="all",
        help="Time filter: hour, day, week, month, year, all",
    )

    # sub-info
    info_parser = subparsers.add_parser("sub-info", help="Get subreddit information")
    info_parser.add_argument(
        "--subreddit", "-s", required=True, help="Subreddit name"
    )

    return parser


def validate_args(args: argparse.Namespace) -> None:
    """Validate argument combinations."""
    if not args.client_id:
        raise CliInputError(
            "Client ID missing. Use --client-id or REDDIT_CLIENT_ID."
        )
    if not args.client_secret:
        raise CliInputError(
            "Client secret missing. Use --client-secret or REDDIT_CLIENT_SECRET."
        )

    if hasattr(args, "limit") and (args.limit <= 0 or args.limit > MAX_LIMIT):
        raise CliInputError(f"--limit must be between 1 and {MAX_LIMIT}.")

    if hasattr(args, "time") and args.time not in VALID_TIME_FILTERS:
        raise CliInputError(
            f"Invalid --time '{args.time}'. Choose from: {', '.join(sorted(VALID_TIME_FILTERS))}."
        )

    if hasattr(args, "sort") and args.sort not in VALID_SORT_OPTIONS:
        raise CliInputError(
            f"Invalid --sort '{args.sort}'. Choose from: {', '.join(sorted(VALID_SORT_OPTIONS))}."
        )


def _render_table(headers: list[str], rows: list[list[Any]]) -> str:
    """Render rows as a plain text table."""
    normalized_rows = [
        ["-" if value is None else str(value) for value in row] for row in rows
    ]
    widths = [len(h) for h in headers]

    for row in normalized_rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))

    header_line = " | ".join(
        header.ljust(widths[i]) for i, header in enumerate(headers)
    )
    separator = "-+-".join("-" * width for width in widths)
    body = [
        " | ".join(value.ljust(widths[i]) for i, value in enumerate(row))
        for row in normalized_rows
    ]

    return "\n".join([header_line, separator, *body])


def _truncate(text: str | None, max_len: int = 60) -> str | None:
    """Truncate text for table display."""
    if text is None:
        return None
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def print_human(command: str, payload: dict[str, Any]) -> None:
    """Print result in human-readable format."""
    if command == "sub-info":
        info = payload["subreddit"]
        fields = [
            ("Name", "name"),
            ("Title", "title"),
            ("Subscribers", "subscribers"),
            ("Active users", "active_users"),
            ("Type", "subreddit_type"),
            ("NSFW", "over_18"),
            ("Created", "created_utc"),
            ("URL", "url"),
            ("Description", "public_description"),
        ]
        for label, key in fields:
            value = info.get(key)
            print(f"{label}: {'-' if value is None else value}")
        return

    # All listing commands (hot, new, top, rising, search)
    subreddit = payload.get("subreddit", "reddit")
    print(f"Subreddit: r/{subreddit}")

    posts = payload.get("posts", [])
    if not posts:
        print("No posts found.")
        return

    rows = [
        [
            _truncate(post.get("title"), 50),
            post.get("score"),
            post.get("num_comments"),
            post.get("author"),
            post.get("link_flair_text"),
        ]
        for post in posts
    ]
    print(
        _render_table(
            ["title", "score", "comments", "author", "flair"],
            rows,
        )
    )


async def _get_token(
    session: ClientSession, client_id: str, client_secret: str
) -> str:
    """Obtain an OAuth2 app-only access token."""
    auth = BasicAuth(client_id, client_secret)
    headers = {"User-Agent": USER_AGENT}
    data = {"grant_type": "client_credentials"}

    async with session.post(
        TOKEN_URL, auth=auth, headers=headers, data=data
    ) as resp:
        if resp.status == 401:
            raise RedditAuthError("Invalid client ID or secret.")
        if resp.status == 429:
            raise RedditApiError("Rate limit exceeded. Try again later.")
        if resp.status != 200:
            raise RedditApiError(f"Token request failed (HTTP {resp.status}).")
        body = await resp.json()

    token = body.get("access_token")
    if not token:
        raise RedditAuthError("No access token in response.")
    return token


async def run_command(args: argparse.Namespace) -> dict[str, Any]:
    """Execute the selected command."""
    timeout = ClientTimeout(total=20)

    async with ClientSession(timeout=timeout) as session:
        token = await _get_token(session, args.client_id, args.client_secret)
        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": USER_AGENT,
        }

        if args.command in LISTING_COMMANDS:
            params: dict[str, str] = {"limit": str(args.limit)}
            if args.command == "top" and hasattr(args, "time"):
                params["t"] = args.time

            url = f"{API_BASE_URL}/r/{args.subreddit}/{args.command}"
            async with session.get(url, headers=headers, params=params) as resp:
                if resp.status == 403:
                    raise RedditApiError(
                        f"Access denied to r/{args.subreddit}. It may be private."
                    )
                if resp.status == 404:
                    raise RedditApiError(f"Subreddit r/{args.subreddit} not found.")
                if resp.status != 200:
                    raise RedditApiError(f"API error (HTTP {resp.status}).")
                listing = await resp.json()

            return {
                "command": args.command,
                "subreddit": args.subreddit,
                "posts": transform_posts(listing),
            }

        if args.command == "search":
            params = {
                "q": args.query,
                "limit": str(args.limit),
                "sort": args.sort,
                "t": args.time,
                "restrict_sr": "true" if args.subreddit else "false",
                "type": "link",
            }
            if args.subreddit:
                url = f"{API_BASE_URL}/r/{args.subreddit}/search"
            else:
                url = f"{API_BASE_URL}/search"

            async with session.get(url, headers=headers, params=params) as resp:
                if resp.status != 200:
                    raise RedditApiError(f"Search failed (HTTP {resp.status}).")
                listing = await resp.json()

            return {
                "command": args.command,
                "subreddit": args.subreddit or "all",
                "query": args.query,
                "posts": transform_posts(listing),
            }

        # sub-info
        url = f"{API_BASE_URL}/r/{args.subreddit}/about"
        async with session.get(url, headers=headers) as resp:
            if resp.status == 404:
                raise RedditApiError(f"Subreddit r/{args.subreddit} not found.")
            if resp.status != 200:
                raise RedditApiError(f"API error (HTTP {resp.status}).")
            data = await resp.json()

        return {
            "command": args.command,
            "subreddit_name": args.subreddit,
            "subreddit": transform_subreddit_info(data),
        }


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        validate_args(args)
        payload = asyncio.run(run_command(args))
    except CliInputError as error:
        print(f"Input error: {error}", file=sys.stderr)
        return 2
    except RedditAuthError as error:
        print(f"Auth error: {error}", file=sys.stderr)
        return 2
    except RedditApiError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except (ClientError, TimeoutError) as error:
        print(f"Error while calling Reddit API: {error}", file=sys.stderr)
        return 1

    if args.json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print_human(args.command, payload)

    return 0
