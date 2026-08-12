"""Read, write, and repair docs/STATE.md.

The file has two halves delimited by HTML comment markers. The facts half is
owned by inject_context.py and rewritten every session. The intent half is
owned by the model and never modified by any script.
"""

from __future__ import annotations

from pathlib import Path

FACTS_BEGIN = "<!-- FACTS:BEGIN -->"
FACTS_END = "<!-- FACTS:END -->"
INTENT_BEGIN = "<!-- INTENT:BEGIN -->"
INTENT_END = "<!-- INTENT:END -->"

INTENT_PLACEHOLDER = "- Decisions: (none recorded yet)\n- Next step: (none recorded yet)"

TEMPLATE = f"""# Project State

Facts below are regenerated automatically at session start. Do not edit them.
Intent below is written by Claude at session end.

{FACTS_BEGIN}
(not yet generated)
{FACTS_END}

## Intent

{INTENT_BEGIN}
{INTENT_PLACEHOLDER}
{INTENT_END}
"""


def state_path(project_root: Path) -> Path:
    return Path(project_root) / "docs" / "STATE.md"


def _extract(text: str, begin: str, end: str) -> str | None:
    start = text.find(begin)
    stop = text.find(end)
    if start == -1 or stop == -1 or stop < start:
        return None
    return text[start + len(begin) : stop].strip()


def _is_well_formed(text: str) -> bool:
    """All four markers present, in order, non-overlapping.

    Presence alone is not enough: a file with FACTS:END before FACTS:BEGIN
    passes a presence check but makes write_facts duplicate the intent half on
    every call, so misordered files must be treated as malformed and repaired.
    """
    positions = [text.find(m) for m in (FACTS_BEGIN, FACTS_END, INTENT_BEGIN, INTENT_END)]
    if any(p == -1 for p in positions):
        return False
    return all(a < b for a, b in zip(positions, positions[1:]))


def ensure_state_file(project_root: Path) -> Path:
    """Guarantee a well-formed STATE.md exists. Recovers intent when possible."""
    path = state_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        text = ""
    if _is_well_formed(text):
        return path
    _regenerate(path, text)
    return path


def _regenerate(path: Path, text: str) -> None:
    """Rewrite from template, recovering the intent body when its markers exist."""
    recovered = _extract(text, INTENT_BEGIN, INTENT_END) or INTENT_PLACEHOLDER
    path.write_text(
        TEMPLATE.replace(INTENT_PLACEHOLDER, recovered, 1), encoding="utf-8"
    )


def read_intent(project_root: Path) -> str:
    """Return the intent body, or the placeholder if unavailable."""
    path = ensure_state_file(project_root)
    text = path.read_text(encoding="utf-8")
    return _extract(text, INTENT_BEGIN, INTENT_END) or INTENT_PLACEHOLDER


def write_facts(project_root: Path, facts_md: str) -> None:
    """Replace the facts half in place, leaving the intent half untouched."""
    path = ensure_state_file(project_root)
    text = path.read_text(encoding="utf-8")
    begin = text.find(FACTS_BEGIN)
    stop = text.find(FACTS_END)
    start = begin + len(FACTS_BEGIN)
    if begin == -1 or stop == -1 or stop <= start:
        # ensure_state_file should have repaired this; if the indices are still
        # not sane, regenerating is the only non-corrupting option.
        _regenerate(path, text)
        text = path.read_text(encoding="utf-8")
        start = text.find(FACTS_BEGIN) + len(FACTS_BEGIN)
        stop = text.find(FACTS_END)
    path.write_text(
        text[:start] + "\n" + facts_md.strip() + "\n" + text[stop:], encoding="utf-8"
    )
