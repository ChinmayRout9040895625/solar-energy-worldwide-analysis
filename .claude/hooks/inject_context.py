"""SessionStart hook: build and inject the compact project state block.

Fails open. Any exception results in no output and exit code 0.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.budget import estimate_tokens, truncate_to_budget
from lib.config import load_config
from lib.facts import collect_facts
from lib.state import read_intent, write_facts
from lib.tokenlog import append_entry

FACTS_ORDER = ("data_schema", "artifacts", "git")
HEADINGS = {
    "data_schema": "Data",
    "artifacts": "Artifacts",
    "git": "Git",
    "memory_index": "Memory notes (read only if relevant)",
    "intent": "Where we left off",
}


def _resolve_root(payload: dict) -> Path:
    for candidate in (payload.get("cwd"), os.environ.get("CLAUDE_PROJECT_DIR")):
        if candidate:
            return Path(candidate)
    return Path.cwd()


def _section(name: str, body: str) -> str:
    return f"### {HEADINGS[name]}\n{body}"


def build_block(project_root: Path, config: dict) -> tuple[str, list[str]]:
    """Return (block_markdown, included_block_names)."""
    blocks = config.get("blocks", {})
    budget = config.get("token_budget", {})
    facts = collect_facts(project_root, blocks)
    included: list[str] = []
    parts: list[str] = []

    facts_md = "\n\n".join(
        _section(name, facts[name]) for name in FACTS_ORDER if name in facts
    )
    if facts_md:
        parts.append(truncate_to_budget(facts_md, budget.get("facts", 400)))
        included.extend(name for name in FACTS_ORDER if name in facts)

    if "memory_index" in facts:
        parts.append(
            truncate_to_budget(
                _section("memory_index", facts["memory_index"]),
                budget.get("memory_index", 100),
            )
        )
        included.append("memory_index")

    if blocks.get("intent", True):
        intent = read_intent(project_root)
        parts.append(
            truncate_to_budget(_section("intent", intent), budget.get("intent", 300))
        )
        included.append("intent")

    # Persist the facts half so the on-disk file stays true.
    write_facts(project_root, facts_md or "(no facts collected)")

    if not parts:
        return "", included
    header = "## Project state (auto-injected, read-only)"
    block = header + "\n\n" + "\n\n".join(p for p in parts if p)
    return truncate_to_budget(block, budget.get("total", 800)), included


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
    config = load_config(root)
    block, included = build_block(root, config)

    if config.get("token_logging", True) and block:
        append_entry(root, estimate_tokens(block), included)

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": block,
        }
    }))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
