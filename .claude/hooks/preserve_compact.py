"""PreCompact hook: persist intent to a memory note before the window resets."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.config import load_config
from lib.hookio import read_payload, resolve_root
from lib.state import read_intent

INSTRUCTION = (
    "When summarizing, preserve the injected project state block verbatim and keep "
    "the intent recorded in docs/STATE.md. Prior intent was also saved to "
    "docs/memory/precompact/ as a pre-compact note."
)


def main() -> None:
    payload = read_payload()
    root = resolve_root(payload)
    if not load_config(root).get("preserve_compact", True):
        return

    intent = read_intent(root)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    # A subdirectory, not docs/memory/ itself: the memory-index glob is
    # non-recursive, so these machine-written notes stay out of the injected
    # index instead of crowding out the human-written ones.
    note = root / "docs" / "memory" / "precompact" / f"pre-compact-{stamp}.md"
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
