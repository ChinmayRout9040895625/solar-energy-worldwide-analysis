"""Append-only record of what each injection cost, so the harness is measurable."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def log_path(project_root: Path) -> Path:
    return Path(project_root) / "docs" / "token_log.jsonl"


def append_entry(project_root: Path, tokens: int, blocks: list[str]) -> None:
    """Append one JSON line. Silently does nothing if the log cannot be written."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tokens": tokens,
        "blocks": blocks,
    }
    try:
        path = log_path(project_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
    except (OSError, ValueError):
        return
