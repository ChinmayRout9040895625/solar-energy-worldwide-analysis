"""PreCompact hook: persist intent to a memory note before the window resets."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.state import read_intent

INSTRUCTION = (
    "When summarizing, preserve the injected project state block verbatim and keep "
    "the intent recorded in docs/STATE.md. Prior intent was also saved to "
    "docs/memory/ as a pre-compact note."
)


def _resolve_root(payload: dict) -> Path:
    for candidate in (os.environ.get("CLAUDE_PROJECT_DIR"), payload.get("cwd")):
        if candidate:
            return Path(candidate)
    return Path.cwd()


def main() -> None:
    try:
        raw = sys.stdin.read()
    except OSError:
        raw = ""
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except ValueError:
        payload = {}

    root = _resolve_root(payload)
    intent = read_intent(root)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    note = root / "docs" / "memory" / f"pre-compact-{stamp}.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(
        f"# Pre-compact snapshot {stamp}\n\n"
        f"Trigger: {payload.get('trigger', 'unknown')}\n\n"
        f"## Intent at compaction\n\n{intent}\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreCompact",
            "additionalContext": INSTRUCTION,
        }
    }))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
