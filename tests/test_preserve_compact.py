import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / ".claude" / "hooks" / "preserve_compact.py"
sys.path.insert(0, str(REPO / ".claude" / "hooks"))

from lib.state import ensure_state_file, state_path


def run_hook(cwd: Path):
    payload = {"hook_event_name": "PreCompact", "cwd": str(cwd), "trigger": "auto"}
    clean_env = dict(os.environ)
    clean_env.pop("CLAUDE_PROJECT_DIR", None)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(cwd),
        timeout=30,
        env=clean_env,
    )


def _seed_intent(tmp_path, text="Next step: finish ROI chart"):
    ensure_state_file(tmp_path)
    path = state_path(tmp_path)
    path.write_text(
        path.read_text(encoding="utf-8").replace("(none recorded yet)", text, 1),
        encoding="utf-8",
    )


def test_writes_precompact_note_containing_intent(tmp_path):
    _seed_intent(tmp_path)
    result = run_hook(tmp_path)
    assert result.returncode == 0
    notes = list((tmp_path / "docs" / "memory" / "precompact").glob("pre-compact-*.md"))
    assert len(notes) == 1
    assert "finish ROI chart" in notes[0].read_text(encoding="utf-8")


def test_note_is_not_written_directly_into_memory_dir(tmp_path):
    _seed_intent(tmp_path)
    run_hook(tmp_path)
    assert list((tmp_path / "docs" / "memory").glob("*.md")) == []


def test_precompact_notes_absent_from_injected_memory_index(tmp_path):
    _seed_intent(tmp_path)
    run_hook(tmp_path)
    from lib.facts import collect_facts

    facts = collect_facts(tmp_path, {"memory_index": True})
    assert "pre-compact" not in facts.get("memory_index", "")


def test_disabled_by_config_writes_nothing_and_prints_nothing(tmp_path):
    _seed_intent(tmp_path)
    cfg = tmp_path / ".claude"
    cfg.mkdir(exist_ok=True)
    (cfg / "context.config.json").write_text(
        json.dumps({"preserve_compact": False}), encoding="utf-8"
    )
    result = run_hook(tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == ""
    assert not (tmp_path / "docs" / "memory" / "precompact").exists()


def test_emits_preservation_instruction(tmp_path):
    _seed_intent(tmp_path)
    result = run_hook(tmp_path)
    assert "STATE.md" in result.stdout


def test_exits_zero_on_empty_project(tmp_path):
    result = run_hook(tmp_path)
    assert result.returncode == 0
