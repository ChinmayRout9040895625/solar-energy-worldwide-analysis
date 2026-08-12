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


def test_gate_disabled_by_config(tmp_path):
    _touch_work_file_after_state(tmp_path)
    cfg = tmp_path / ".claude"
    cfg.mkdir(exist_ok=True)
    (cfg / "context.config.json").write_text(
        json.dumps({"checkpoint_gate": False}), encoding="utf-8"
    )
    result = run_hook(tmp_path)
    assert result.stdout.strip() == ""
