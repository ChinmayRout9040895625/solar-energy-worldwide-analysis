"""Collect the cheap, deterministic half of the state block.

Stdlib only. Every collector returns None on any problem so a single bad
input can never take down the injection.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

MAX_COLUMNS_SHOWN = 20
MAX_FILES_SHOWN = 15
MAX_MEMORY_NOTES = 12
MAX_DESCRIPTION_CHARS = 120
ARTIFACT_DIRS = ("analysis", "output")


def _csv_summary(path: Path) -> str | None:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            header = handle.readline().strip()
            if not header:
                return None
            rows = sum(1 for _ in handle)
    except OSError:
        return None
    columns = header.split(",")
    shown = columns[:MAX_COLUMNS_SHOWN]
    suffix = f" (+{len(columns) - len(shown)} more)" if len(columns) > len(shown) else ""
    return f"- `{path.name}`: {rows} rows, {len(columns)} cols — {', '.join(shown)}{suffix}"


def _data_schema(root: Path) -> str | None:
    lines = [s for p in sorted(root.glob("*.csv")) if (s := _csv_summary(p))]
    return "\n".join(lines) if lines else None


def _artifacts(root: Path) -> str | None:
    all_files: list[Path] = []
    for name in ARTIFACT_DIRS:
        directory = root / name
        if not directory.is_dir():
            continue
        all_files.extend(sorted(p for p in directory.rglob("*") if p.is_file()))
    if not all_files:
        return None
    shown = all_files[:MAX_FILES_SHOWN]
    lines = [f"- {path.relative_to(root).as_posix()}" for path in shown]
    if len(all_files) > MAX_FILES_SHOWN:
        lines.append(f"- (+{len(all_files) - MAX_FILES_SHOWN} more)")
    return "\n".join(lines)


def _git(root: Path) -> str | None:
    if not (root / ".git").exists():
        return None
    try:
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=root, capture_output=True, text=True, timeout=5,
        )
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root, capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if branch.returncode != 0:
        return None
    dirty = [line for line in status.stdout.splitlines() if line.strip()]
    return f"- branch `{branch.stdout.strip()}`, {len(dirty)} uncommitted file(s)"


def _description(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if stripped:
                desc = stripped.lstrip("# ").strip()
                if len(desc) > MAX_DESCRIPTION_CHARS:
                    desc = desc[:MAX_DESCRIPTION_CHARS].rstrip() + "…"
                return desc
    except OSError:
        pass
    return "(empty)"


def _memory_index(root: Path) -> str | None:
    directory = root / "docs" / "memory"
    if not directory.is_dir():
        return None
    notes = sorted(p for p in directory.glob("*.md") if p.is_file())
    lines = [
        f"- {p.relative_to(root).as_posix()} — {_description(p)}"
        for p in notes[:MAX_MEMORY_NOTES]
    ]
    if len(notes) > MAX_MEMORY_NOTES:
        lines.append(f"- (+{len(notes) - MAX_MEMORY_NOTES} more notes)")
    return "\n".join(lines) if lines else None


COLLECTORS = {
    "data_schema": _data_schema,
    "artifacts": _artifacts,
    "git": _git,
    "memory_index": _memory_index,
}


def collect_facts(project_root: Path, blocks: dict) -> dict[str, str]:
    """Return {block_name: markdown} for enabled blocks that produced content."""
    root = Path(project_root)
    result: dict[str, str] = {}
    for name, collector in COLLECTORS.items():
        if not blocks.get(name, False):
            continue
        try:
            body = collector(root)
        except Exception:
            body = None
        if body:
            result[name] = body
    return result
