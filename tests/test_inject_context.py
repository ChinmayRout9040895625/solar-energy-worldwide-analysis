import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / ".claude" / "hooks" / "inject_context.py"
sys.path.insert(0, str(REPO / ".claude" / "hooks"))

from lib.config import DEFAULT_CONFIG
from lib.state import read_intent, state_path


def run_hook(cwd: Path, payload: dict | None = None, env: dict | None = None):
    payload = payload or {"hook_event_name": "SessionStart", "cwd": str(cwd)}
    clean_env = dict(os.environ)
    clean_env.pop("CLAUDE_PROJECT_DIR", None)
    if env:
        clean_env.update(env)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(cwd),
        timeout=30,
        env=clean_env,
    )


def _make_project(tmp_path):
    (tmp_path / "solar.csv").write_text("City,GHI\nDelhi,5.5\n", encoding="utf-8")
    return tmp_path


def test_empty_project_exits_zero_with_valid_json(tmp_path):
    result = run_hook(tmp_path)
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"


def test_populated_project_includes_schema_in_context(tmp_path):
    _make_project(tmp_path)
    result = run_hook(tmp_path)
    assert result.returncode == 0
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "solar.csv" in context


def test_hook_rewrites_facts_into_state_file(tmp_path):
    _make_project(tmp_path)
    run_hook(tmp_path)
    assert "solar.csv" in state_path(tmp_path).read_text(encoding="utf-8")


def test_hook_preserves_existing_intent(tmp_path):
    _make_project(tmp_path)
    run_hook(tmp_path)
    path = state_path(tmp_path)
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "(none recorded yet)", "finish the ROI chart", 1
        ),
        encoding="utf-8",
    )
    run_hook(tmp_path)
    assert "finish the ROI chart" in read_intent(tmp_path)


def test_malformed_config_still_produces_output(tmp_path):
    _make_project(tmp_path)
    cfg = tmp_path / ".claude"
    cfg.mkdir()
    (cfg / "context.config.json").write_text("{broken", encoding="utf-8")
    result = run_hook(tmp_path)
    assert result.returncode == 0
    assert json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]


def test_oversized_memory_index_is_truncated_to_total_budget(tmp_path):
    _make_project(tmp_path)
    mem = tmp_path / "docs" / "memory"
    mem.mkdir(parents=True)
    for i in range(60):
        (mem / f"note{i:03d}.md").write_text(f"# note {i} " + "x" * 4000, encoding="utf-8")
    result = run_hook(tmp_path)
    assert result.returncode == 0
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert len(context) <= DEFAULT_CONFIG["token_budget"]["total"] * 4 + 40


def test_all_blocks_disabled_yields_empty_context(tmp_path):
    _make_project(tmp_path)
    cfg = tmp_path / ".claude"
    cfg.mkdir()
    (cfg / "context.config.json").write_text(
        json.dumps({"blocks": dict.fromkeys(
            ["data_schema", "artifacts", "git", "intent", "memory_index"], False)}),
        encoding="utf-8",
    )
    result = run_hook(tmp_path)
    assert result.returncode == 0
    assert json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"] == ""


def test_writes_token_log_entry(tmp_path):
    _make_project(tmp_path)
    run_hook(tmp_path)
    log = tmp_path / "docs" / "token_log.jsonl"
    assert json.loads(log.read_text(encoding="utf-8").strip().splitlines()[0])["tokens"] > 0


def test_intent_survives_total_budget_pressure(tmp_path):
    _make_project(tmp_path)
    mem = tmp_path / "docs" / "memory"
    mem.mkdir(parents=True)
    for i in range(60):
        (mem / f"note{i:03d}.md").write_text(f"# note {i} " + "x" * 4000, encoding="utf-8")
    # Prime the state file, then inject a distinctive intent before running.
    run_hook(tmp_path)
    marker = "DISTINCTIVE_INTENT_MARKER_KEEP_ME"
    path = state_path(tmp_path)
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "(none recorded yet)", marker, 1
        ),
        encoding="utf-8",
    )
    result = run_hook(tmp_path)
    assert result.returncode == 0
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert marker in context
    assert len(context) <= DEFAULT_CONFIG["token_budget"]["total"] * 4 + 40


def test_claude_project_dir_wins_over_payload_cwd(tmp_path):
    populated = tmp_path / "populated"
    empty = tmp_path / "empty"
    populated.mkdir()
    empty.mkdir()
    _make_project(populated)
    result = run_hook(
        empty,
        payload={"hook_event_name": "SessionStart", "cwd": str(empty)},
        env={"CLAUDE_PROJECT_DIR": str(populated)},
    )
    assert result.returncode == 0
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "solar.csv" in context
    assert state_path(populated).exists()
    assert "solar.csv" in state_path(populated).read_text(encoding="utf-8")
    assert not state_path(empty).exists()
