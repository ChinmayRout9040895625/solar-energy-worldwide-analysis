"""Cheap token estimation and hard truncation for injected context."""

from __future__ import annotations

CHARS_PER_TOKEN = 4
TRUNCATION_MARKER = "\n[truncated]"


def estimate_tokens(text: str) -> int:
    """Approximate token count. Deliberately crude; only used for budgeting."""
    if not text:
        return 0
    return (len(text) + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN


def truncate_to_budget(text: str, max_tokens: int) -> str:
    """Cut text to fit max_tokens, appending a visible marker when cut."""
    if max_tokens <= 0:
        return ""
    limit = max_tokens * CHARS_PER_TOKEN
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + TRUNCATION_MARKER
