"""Stop hook: ensure this session's intent got recorded in docs/STATE.md.

A hook cannot generate text itself, so when intent is missing this returns a
block decision, handing control back to the model to perform the write.
Guarded by stop_hook_active so it can fire at most once and never loops.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.config import load_config
from lib.state import state_path

WORK_DIRS = ("analysis", "output", "docs/memory")

REASON = (
    "Before stopping: append this session's decisions and the concrete next step "
    "to the intent section of docs/STATE.md (between the INTENT:BEGIN and "
    "INTENT:END markers). Keep it under 150 words. Then stop."
)


def _resolve_root(payload: dict) -> Path:
    env_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_dir:
        return Path(env_dir)
    cwd = payload.get("cwd")
    if cwd:
        return Path(cwd)
    return Path.cwd()


def needs_checkpoint(project_root: Path) -> bool:
    """True when work files are newer than STATE.md."""
    root = Path(project_root)
    state = state_path(root)
    if not state.exists():
        return False
    state_mtime = state.stat().st_mtime
    for name in WORK_DIRS:
        directory = root / name
        if not directory.is_dir():
            continue
        for path in directory.rglob("*"):
            try:
                if path.is_file() and path.stat().st_mtime > state_mtime:
                    return True
            except OSError:
                continue
    return False


def main() -> None:
    try:
        raw = sys.stdin.read()
    except OSError:
        raw = ""
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except ValueError:
        payload = {}

    if payload.get("stop_hook_active"):
        return

    root = _resolve_root(payload)
    if not load_config(root).get("checkpoint_gate", True):
        return
    if not needs_checkpoint(root):
        return

    print(json.dumps({"decision": "block", "reason": REASON}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
