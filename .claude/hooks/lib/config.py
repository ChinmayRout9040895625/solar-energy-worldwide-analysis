"""Load the harness config, merging user values over documented defaults."""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_CONFIG = {
    "verbosity": "lean",
    "token_budget": {"total": 800, "facts": 400, "intent": 300, "memory_index": 100},
    "blocks": {
        "data_schema": True,
        "artifacts": True,
        "git": True,
        "intent": True,
        "memory_index": True,
    },
    "delegation": {"enabled": True, "min_task_size": "multi-step"},
    "checkpoint_gate": True,
    "token_logging": True,
}


def _fresh_defaults() -> dict:
    return json.loads(json.dumps(DEFAULT_CONFIG))


def load_config(project_root: Path) -> dict:
    """Return the effective config. Never raises; falls back to defaults."""
    merged = _fresh_defaults()
    path = Path(project_root) / ".claude" / "context.config.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return merged
    if not isinstance(raw, dict):
        return merged
    for key, value in raw.items():
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key].update(value)
        else:
            merged[key] = value
    return merged
