import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".claude" / "hooks"))

from lib.config import DEFAULT_CONFIG, load_config


def test_shipped_config_matches_defaults_key_for_key():
    repo = Path(__file__).resolve().parents[1]
    shipped = json.loads(
        (repo / ".claude" / "context.config.json").read_text(encoding="utf-8")
    )
    assert set(shipped) == set(DEFAULT_CONFIG)
    for key, value in DEFAULT_CONFIG.items():
        if isinstance(value, dict):
            assert set(shipped[key]) == set(value)


def test_missing_config_returns_defaults(tmp_path):
    assert load_config(tmp_path) == DEFAULT_CONFIG


def test_malformed_config_returns_defaults(tmp_path):
    cfg = tmp_path / ".claude"
    cfg.mkdir()
    (cfg / "context.config.json").write_text("{not json", encoding="utf-8")
    assert load_config(tmp_path) == DEFAULT_CONFIG


def test_partial_config_merges_over_defaults(tmp_path):
    cfg = tmp_path / ".claude"
    cfg.mkdir()
    (cfg / "context.config.json").write_text(
        json.dumps({"verbosity": "explain", "blocks": {"git": False}}), encoding="utf-8"
    )
    result = load_config(tmp_path)
    assert result["verbosity"] == "explain"
    assert result["blocks"]["git"] is False
    assert result["blocks"]["intent"] is True
    assert result["token_budget"]["total"] == 800


def test_load_config_does_not_mutate_defaults(tmp_path):
    cfg = tmp_path / ".claude"
    cfg.mkdir()
    (cfg / "context.config.json").write_text(
        json.dumps({"blocks": {"git": False}}), encoding="utf-8"
    )
    load_config(tmp_path)
    assert DEFAULT_CONFIG["blocks"]["git"] is True
