"""Constants and mappings for the Reddit CLI."""

from __future__ import annotations

from typing import Final

API_BASE_URL: Final = "https://oauth.reddit.com"
TOKEN_URL: Final = "https://www.reddit.com/api/v1/access_token"
USER_AGENT: Final = "reddit-cli/0.1.0"

DEFAULT_LIMIT: Final = 10
MAX_LIMIT: Final = 100

VALID_TIME_FILTERS: Final = frozenset({"hour", "day", "week", "month", "year", "all"})
VALID_SORT_OPTIONS: Final = frozenset({"relevance", "hot", "top", "new", "comments"})

LISTING_COMMANDS: Final = frozenset({"hot", "new", "top", "rising"})
