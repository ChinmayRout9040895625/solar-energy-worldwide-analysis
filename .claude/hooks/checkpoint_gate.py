"""Stop hook: ensure this session's intent got recorded in docs/STATE.md.

A hook cannot generate text itself, so when intent is missing this returns a
block decision, handing control back to the model to perform the write.
Guarded by stop_hook_active so it can fire at most once and never loops.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.config import DEFAULT_CONFIG, load_config
from lib.hookio import read_payload, resolve_root
from lib.state import state_path

FALLBACK_WORK_DIRS = list(DEFAULT_CONFIG["work_dirs"])
FALLBACK_WORK_GLOBS = list(DEFAULT_CONFIG["work_globs"])

REASON = (
    "Before stopping: append this session's decisions and the concrete next step "
    "to the intent section of docs/STATE.md (between the INTENT:BEGIN and "
    "INTENT:END markers). Keep it under 150 words. Then stop."
)


def _string_list(value, fallback: list[str]) -> list[str]:
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return value
    return fallback


def _work_files(root: Path, config: dict):
    """Yield candidate work files: anything under a work_dir, plus root globs.

    Root-level globs are matched non-recursively so that work done before
    analysis/ exists still counts.
    """
    for name in _string_list(config.get("work_dirs"), FALLBACK_WORK_DIRS):
        directory = root / name
        if not directory.is_dir():
            continue
        yield from directory.rglob("*")
    for pattern in _string_list(config.get("work_globs"), FALLBACK_WORK_GLOBS):
        yield from root.glob(pattern)


def needs_checkpoint(project_root: Path, config: dict | None = None) -> bool:
    """True when work files are newer than STATE.md."""
    root = Path(project_root)
    config = config if isinstance(config, dict) else {}
    state = state_path(root)
    if not state.exists():
        return False
    state_mtime = state.stat().st_mtime
    for path in _work_files(root, config):
        try:
            if path.is_file() and path.stat().st_mtime > state_mtime:
                return True
        except OSError:
            continue
    return False


def main() -> None:
    payload = read_payload()
    if payload.get("stop_hook_active"):
        return

    root = resolve_root(payload)
    config = load_config(root)
    if not config.get("checkpoint_gate", True):
        return
    if not needs_checkpoint(root, config):
        return

    print(json.dumps({"decision": "block", "reason": REASON}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
