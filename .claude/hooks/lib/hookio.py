"""Shared hook plumbing: root resolution and stdin payload parsing.

Every hook needs exactly these two things before it can do anything, and all
three must fail open, so the failure handling lives here once.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def resolve_root(payload: dict) -> Path:
    """CLAUDE_PROJECT_DIR when set and non-empty, then payload cwd, then cwd."""
    if not isinstance(payload, dict):
        payload = {}
    for candidate in (os.environ.get("CLAUDE_PROJECT_DIR"), payload.get("cwd")):
        if candidate:
            return Path(candidate)
    return Path.cwd()


def read_payload() -> dict:
    """Read stdin and return the parsed hook payload, or {} on any problem."""
    try:
        raw = sys.stdin.read()
    except OSError:
        return {}
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}
