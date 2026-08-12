import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".claude" / "hooks"))

from lib.state import (
    INTENT_BEGIN,
    INTENT_END,
    ensure_state_file,
    read_intent,
    state_path,
    write_facts,
)


def test_ensure_creates_file_with_all_markers(tmp_path):
    path = ensure_state_file(tmp_path)
    assert path == state_path(tmp_path)
    text = path.read_text(encoding="utf-8")
    for marker in ("FACTS:BEGIN", "FACTS:END", "INTENT:BEGIN", "INTENT:END"):
        assert marker in text


def test_write_facts_replaces_only_the_facts_half(tmp_path):
    ensure_state_file(tmp_path)
    write_facts(tmp_path, "- rows: 47")
    write_facts(tmp_path, "- rows: 48")
    text = state_path(tmp_path).read_text(encoding="utf-8")
    assert "- rows: 48" in text
    assert "- rows: 47" not in text


def test_write_facts_preserves_intent(tmp_path):
    ensure_state_file(tmp_path)
    path = state_path(tmp_path)
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        f"{INTENT_BEGIN}\n", f"{INTENT_BEGIN}\nNext step: build ROI chart\n", 1
    )
    path.write_text(text, encoding="utf-8")
    write_facts(tmp_path, "- rows: 47")
    assert "Next step: build ROI chart" in read_intent(tmp_path)


def test_read_intent_returns_only_intent_body(tmp_path):
    ensure_state_file(tmp_path)
    write_facts(tmp_path, "- SECRET_FACT")
    assert "SECRET_FACT" not in read_intent(tmp_path)


def test_malformed_file_is_repaired_not_raised(tmp_path):
    path = state_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("garbage with no markers at all", encoding="utf-8")
    ensure_state_file(tmp_path)
    assert INTENT_END in path.read_text(encoding="utf-8")


def test_malformed_file_recovers_intent_when_markers_present(tmp_path):
    path = state_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"no facts markers\n{INTENT_BEGIN}\nkeep me\n{INTENT_END}\n", encoding="utf-8"
    )
    ensure_state_file(tmp_path)
    assert "keep me" in read_intent(tmp_path)
