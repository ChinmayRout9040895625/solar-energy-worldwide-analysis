import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / ".claude" / "hooks" / "checkpoint_gate.py"
sys.path.insert(0, str(REPO / ".claude" / "hooks"))

from lib.state import ensure_state_file, state_path


def run_hook(cwd: Path, stop_hook_active=False):
    payload = {
        "hook_event_name": "Stop",
        "cwd": str(cwd),
        "stop_hook_active": stop_hook_active,
    }
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


def _touch_work_file_after_state(tmp_path):
    ensure_state_file(tmp_path)
    old = time.time() - 60
    os.utime(state_path(tmp_path), (old, old))
    work = tmp_path / "analysis"
    work.mkdir(exist_ok=True)
    (work / "roi.py").write_text("print(1)", encoding="utf-8")


def test_no_work_files_means_no_block(tmp_path):
    ensure_state_file(tmp_path)
    result = run_hook(tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_stale_state_triggers_block_with_reason(tmp_path):
    _touch_work_file_after_state(tmp_path)
    result = run_hook(tmp_path)
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["decision"] == "block"
    assert "STATE.md" in payload["reason"]


def test_never_blocks_twice_when_stop_hook_active(tmp_path):
    _touch_work_file_after_state(tmp_path)
    result = run_hook(tmp_path, stop_hook_active=True)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_state_newer_than_work_means_no_block(tmp_path):
    work = tmp_path / "analysis"
    work.mkdir(parents=True)
    (work / "roi.py").write_text("print(1)", encoding="utf-8")
    old = time.time() - 60
    os.utime(work / "roi.py", (old, old))
    ensure_state_file(tmp_path)
    result = run_hook(tmp_path)
    assert result.stdout.strip() == ""


def test_root_level_py_file_trips_gate_without_analysis_dir(tmp_path):
    """The loop must close before analysis/ exists, or it never closes at all."""
    ensure_state_file(tmp_path)
    old = time.time() - 60
    os.utime(state_path(tmp_path), (old, old))
    (tmp_path / "roi.py").write_text("print(1)", encoding="utf-8")
    assert not (tmp_path / "analysis").exists()
    result = run_hook(tmp_path)
    assert json.loads(result.stdout)["decision"] == "block"


def test_configured_work_dir_is_honored(tmp_path):
    ensure_state_file(tmp_path)
    old = time.time() - 60
    os.utime(state_path(tmp_path), (old, old))
    cfg = tmp_path / ".claude"
    cfg.mkdir(exist_ok=True)
    (cfg / "context.config.json").write_text(
        json.dumps({"work_dirs": ["notebooks"], "work_globs": []}), encoding="utf-8"
    )
    (tmp_path / "notebooks").mkdir()
    (tmp_path / "notebooks" / "scratch.txt").write_text("x", encoding="utf-8")
    result = run_hook(tmp_path)
    assert json.loads(result.stdout)["decision"] == "block"


def test_unconfigured_dir_does_not_trip_gate(tmp_path):
    ensure_state_file(tmp_path)
    old = time.time() - 60
    os.utime(state_path(tmp_path), (old, old))
    cfg = tmp_path / ".claude"
    cfg.mkdir(exist_ok=True)
    (cfg / "context.config.json").write_text(
        json.dumps({"work_dirs": ["analysis"], "work_globs": []}), encoding="utf-8"
    )
    (tmp_path / "elsewhere").mkdir()
    (tmp_path / "elsewhere" / "f.py").write_text("x", encoding="utf-8")
    result = run_hook(tmp_path)
    assert result.stdout.strip() == ""


def test_precompact_notes_do_not_trip_gate(tmp_path):
    """A compaction with no user work must not fire the gate."""
    ensure_state_file(tmp_path)
    old = time.time() - 60
    os.utime(state_path(tmp_path), (old, old))
    notes = tmp_path / "docs" / "memory" / "precompact"
    notes.mkdir(parents=True)
    (notes / "pre-compact-x.md").write_text("note", encoding="utf-8")
    result = run_hook(tmp_path)
    assert result.stdout.strip() == ""


def test_malformed_work_dirs_config_falls_back(tmp_path):
    ensure_state_file(tmp_path)
    old = time.time() - 60
    os.utime(state_path(tmp_path), (old, old))
    cfg = tmp_path / ".claude"
    cfg.mkdir(exist_ok=True)
    (cfg / "context.config.json").write_text(
        json.dumps({"work_dirs": "analysis", "work_globs": [1, 2]}), encoding="utf-8"
    )
    (tmp_path / "roi.py").write_text("print(1)", encoding="utf-8")
    result = run_hook(tmp_path)
    assert result.returncode == 0
    assert json.loads(result.stdout)["decision"] == "block"


def test_gate_disabled_by_config(tmp_path):
    _touch_work_file_after_state(tmp_path)
    cfg = tmp_path / ".claude"
    cfg.mkdir(exist_ok=True)
    (cfg / "context.config.json").write_text(
        json.dumps({"checkpoint_gate": False}), encoding="utf-8"
    )
    result = run_hook(tmp_path)
    assert result.stdout.strip() == ""
