"""SessionStart hook: build and inject the compact project state block.

Fails open. Any exception results in no output and exit code 0.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.budget import estimate_tokens, truncate_to_budget
from lib.config import load_config
from lib.facts import collect_facts
from lib.hookio import read_payload, resolve_root
from lib.state import read_intent, write_facts
from lib.tokenlog import append_entry

FACTS_ORDER = ("data_schema", "artifacts", "git")
BLOCK_NAMES = FACTS_ORDER + ("intent", "memory_index")
HEADINGS = {
    "data_schema": "Data",
    "artifacts": "Artifacts",
    "git": "Git",
    "memory_index": "Memory notes (read only if relevant)",
    "intent": "Where we left off",
}


def _section(name: str, body: str) -> str:
    return f"### {HEADINGS[name]}\n{body}"


def build_block(
    project_root: Path, config: dict, persist_facts: bool = True
) -> tuple[str, list[str]]:
    """Return (block_markdown, included_block_names).

    With every block disabled this is a genuine no-op: no collector runs, no
    git subprocess is spawned, and STATE.md is left untouched.
    """
    blocks = config.get("blocks", {})
    budget = config.get("token_budget", {})
    if not any(blocks.get(name, True) for name in BLOCK_NAMES):
        return "", []
    facts = collect_facts(project_root, blocks)
    included: list[str] = []
    parts: list[str] = []

    # Intent goes first: a total-budget truncation (which cuts from the end)
    # must sacrifice regenerable facts before it touches the model's own
    # unrecoverable notes.
    if blocks.get("intent", True):
        intent = read_intent(project_root)
        parts.append(
            truncate_to_budget(_section("intent", intent), budget.get("intent", 300))
        )
        included.append("intent")

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

    # Persist the facts half so the on-disk file stays true — but only when the
    # facts blocks are actually enabled and the session source permits a write.
    if persist_facts and any(blocks.get(name, True) for name in FACTS_ORDER):
        write_facts(project_root, facts_md or "(no facts collected)")

    if not parts:
        return "", included
    header = "## Project state (auto-injected, read-only)"
    block = header + "\n\n" + "\n\n".join(p for p in parts if p)
    return truncate_to_budget(block, budget.get("total", 800)), included


def main() -> None:
    payload = read_payload()
    root = resolve_root(payload)
    config = load_config(root)

    # A resume or a mid-session compaction must not touch STATE.md: rewriting it
    # bumps its mtime to now, which would retroactively make every work file
    # written earlier this session look older than STATE.md and erase the
    # checkpoint gate's evidence. The block is still emitted — the model needs
    # its context back after a compaction. Anything unexpected behaves as
    # startup, the conservative default.
    source = payload.get("source")
    persist_facts = source not in ("resume", "compact")

    block, included = build_block(root, config, persist_facts=persist_facts)

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
