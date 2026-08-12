# Context Management Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a project-local, token-optimized context management harness that auto-injects a compact self-refreshing state block at session start, routes mechanical work to Sonnet subagents while Opus 5 handles reasoning, and enforces terse output.

**Architecture:** Three Python hooks (`SessionStart`, `Stop`, `PreCompact`) sit on top of four small shared library modules under `.claude/hooks/lib/`. All hooks read one config file at runtime and all fail open — any exception prints nothing and exits 0. State lives in `docs/STATE.md`, split into a script-owned facts half and a model-owned intent half by HTML comment markers.

**Tech Stack:** Python 3.14 (stdlib only for hooks — no pandas dependency in the hook path), pytest for tests, Claude Code hooks + agent frontmatter for wiring.

## Global Constraints

- **Hooks fail open, always.** Every hook's `main()` is wrapped in `try/except Exception`; on any error it prints nothing and exits 0. A broken hook must never block a session.
- **Hook path is stdlib-only.** No pandas, no third-party imports inside `.claude/hooks/`. Startup must stay under 1 second.
- **Token ceiling:** injected block total 800 tokens; sub-budgets facts 400, intent 300, memory_index 100.
- **Injection frequency:** once per session via `SessionStart`. Never `UserPromptSubmit`.
- **Config is the single source of truth:** `.claude/context.config.json`. Missing or malformed → documented defaults, never an error.
- **Worker agents declare `model: sonnet`** and must be instructed to return a digest, not a transcript.
- **Python invocation in hooks:** `python "$CLAUDE_PROJECT_DIR/.claude/hooks/<name>.py"`.
- **Commit after every task.**

## Deviation from spec (flagged)

The spec described `checkpoint_gate.py` as inspecting the transcript. This plan uses **file mtime comparison** instead (work files newer than `docs/STATE.md` ⇒ intent not recorded). It is deterministic, far simpler to test, and does not depend on transcript format. Same outcome, less fragility.

## File Structure

| File | Responsibility |
|---|---|
| `.claude/hooks/lib/config.py` | Load + merge config over defaults |
| `.claude/hooks/lib/budget.py` | Token estimation and truncation |
| `.claude/hooks/lib/state.py` | Read/write/repair `docs/STATE.md` |
| `.claude/hooks/lib/facts.py` | Collect deterministic facts blocks |
| `.claude/hooks/lib/tokenlog.py` | Append entries to `token_log.jsonl` |
| `.claude/hooks/inject_context.py` | SessionStart: assemble + emit block |
| `.claude/hooks/checkpoint_gate.py` | Stop: ensure intent was recorded |
| `.claude/hooks/preserve_compact.py` | PreCompact: persist intent before window reset |
| `.claude/context.config.json` | All knobs |
| `.claude/settings.json` | Hook wiring, model, effortLevel |
| `.claude/agents/*.md` | Four Sonnet workers |
| `CLAUDE.md` | Response contract + routing policy |
| `docs/STATE.md` | Living state |
| `tests/test_*.py` | Unit tests |

---

### Task 1: Repository init and config loader

**Files:**
- Create: `.gitignore`
- Create: `.claude/hooks/lib/__init__.py` (empty)
- Create: `.claude/hooks/lib/config.py`
- Create: `.claude/context.config.json`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: nothing
- Produces: `DEFAULT_CONFIG: dict`, `load_config(project_root: Path) -> dict`

- [ ] **Step 1: Initialize the repository**

```bash
cd "c:/Users/chinm/Downloads/solar_energy_worldwide_analysis"
git init
```

- [ ] **Step 2: Create `.gitignore`**

```
__pycache__/
*.pyc
.pytest_cache/
docs/token_log.jsonl
docs/memory/pre-compact-*.md
```

- [ ] **Step 3: Create the empty package marker**

Create `.claude/hooks/lib/__init__.py` as an empty file.

- [ ] **Step 4: Write the failing test**

Create `tests/test_config.py`:

```python
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".claude" / "hooks"))

from lib.config import DEFAULT_CONFIG, load_config


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
```

- [ ] **Step 5: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lib.config'`

- [ ] **Step 6: Write the implementation**

Create `.claude/hooks/lib/config.py`:

```python
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
```

- [ ] **Step 7: Run test to verify it passes**

Run: `python -m pytest tests/test_config.py -v`
Expected: 4 passed

- [ ] **Step 8: Create the real config file**

Create `.claude/context.config.json`:

```json
{
  "verbosity": "lean",
  "token_budget": { "total": 800, "facts": 400, "intent": 300, "memory_index": 100 },
  "blocks": {
    "data_schema": true,
    "artifacts": true,
    "git": true,
    "intent": true,
    "memory_index": true
  },
  "delegation": { "enabled": true, "min_task_size": "multi-step" },
  "checkpoint_gate": true,
  "token_logging": true
}
```

- [ ] **Step 9: Commit**

```bash
git add .gitignore .claude/context.config.json .claude/hooks/lib/ tests/test_config.py docs/
git commit -m "feat: add harness config loader with default fallback"
```

---

### Task 2: Token budget helpers

**Files:**
- Create: `.claude/hooks/lib/budget.py`
- Test: `tests/test_budget.py`

**Interfaces:**
- Consumes: nothing
- Produces: `estimate_tokens(text: str) -> int`, `truncate_to_budget(text: str, max_tokens: int) -> str`

- [ ] **Step 1: Write the failing test**

Create `tests/test_budget.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".claude" / "hooks"))

from lib.budget import TRUNCATION_MARKER, estimate_tokens, truncate_to_budget


def test_estimate_tokens_uses_four_chars_per_token():
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("abcde") == 2


def test_text_under_budget_is_unchanged():
    text = "short line"
    assert truncate_to_budget(text, 100) == text


def test_text_over_budget_is_truncated_and_marked():
    text = "x" * 1000
    result = truncate_to_budget(text, 10)
    assert result.endswith(TRUNCATION_MARKER)
    assert len(result) <= 40 + len(TRUNCATION_MARKER)


def test_zero_or_negative_budget_yields_empty_string():
    assert truncate_to_budget("anything", 0) == ""
    assert truncate_to_budget("anything", -5) == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_budget.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lib.budget'`

- [ ] **Step 3: Write the implementation**

Create `.claude/hooks/lib/budget.py`:

```python
"""Cheap token estimation and hard truncation for injected context."""

from __future__ import annotations

CHARS_PER_TOKEN = 4
TRUNCATION_MARKER = "\n[truncated]"


def estimate_tokens(text: str) -> int:
    """Approximate token count. Deliberately crude; only used for budgeting."""
    if not text:
        return 0
    return (len(text) + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN


def truncate_to_budget(text: str, max_tokens: int) -> str:
    """Cut text to fit max_tokens, appending a visible marker when cut."""
    if max_tokens <= 0:
        return ""
    limit = max_tokens * CHARS_PER_TOKEN
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + TRUNCATION_MARKER
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_budget.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add .claude/hooks/lib/budget.py tests/test_budget.py
git commit -m "feat: add token budget estimation and truncation"
```

---

### Task 3: STATE.md read, write, and repair

**Files:**
- Create: `.claude/hooks/lib/state.py`
- Test: `tests/test_state.py`

**Interfaces:**
- Consumes: nothing
- Produces: `state_path(project_root: Path) -> Path`, `ensure_state_file(project_root: Path) -> Path`, `read_intent(project_root: Path) -> str`, `write_facts(project_root: Path, facts_md: str) -> None`, and the marker constants `FACTS_BEGIN`, `FACTS_END`, `INTENT_BEGIN`, `INTENT_END`

The facts half is script-owned and overwritten on every session start. The intent half is model-owned and never touched by scripts. A file missing any of the four markers is treated as malformed and regenerated from template — the intent half is preserved if it can be recovered, otherwise reset to the template placeholder.

- [ ] **Step 1: Write the failing test**

Create `tests/test_state.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_state.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lib.state'`

- [ ] **Step 3: Write the implementation**

Create `.claude/hooks/lib/state.py`:

```python
"""Read, write, and repair docs/STATE.md.

The file has two halves delimited by HTML comment markers. The facts half is
owned by inject_context.py and rewritten every session. The intent half is
owned by the model and never modified by any script.
"""

from __future__ import annotations

from pathlib import Path

FACTS_BEGIN = "<!-- FACTS:BEGIN -->"
FACTS_END = "<!-- FACTS:END -->"
INTENT_BEGIN = "<!-- INTENT:BEGIN -->"
INTENT_END = "<!-- INTENT:END -->"

INTENT_PLACEHOLDER = "- Decisions: (none recorded yet)\n- Next step: (none recorded yet)"

TEMPLATE = f"""# Project State

Facts below are regenerated automatically at session start. Do not edit them.
Intent below is written by Claude at session end.

{FACTS_BEGIN}
(not yet generated)
{FACTS_END}

## Intent

{INTENT_BEGIN}
{INTENT_PLACEHOLDER}
{INTENT_END}
"""


def state_path(project_root: Path) -> Path:
    return Path(project_root) / "docs" / "STATE.md"


def _extract(text: str, begin: str, end: str) -> str | None:
    start = text.find(begin)
    stop = text.find(end)
    if start == -1 or stop == -1 or stop < start:
        return None
    return text[start + len(begin) : stop].strip()


def _is_well_formed(text: str) -> bool:
    return all(m in text for m in (FACTS_BEGIN, FACTS_END, INTENT_BEGIN, INTENT_END))


def ensure_state_file(project_root: Path) -> Path:
    """Guarantee a well-formed STATE.md exists. Recovers intent when possible."""
    path = state_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        text = ""
    if _is_well_formed(text):
        return path
    recovered = _extract(text, INTENT_BEGIN, INTENT_END) or INTENT_PLACEHOLDER
    path.write_text(
        TEMPLATE.replace(INTENT_PLACEHOLDER, recovered), encoding="utf-8"
    )
    return path


def read_intent(project_root: Path) -> str:
    """Return the intent body, or the placeholder if unavailable."""
    path = ensure_state_file(project_root)
    text = path.read_text(encoding="utf-8")
    return _extract(text, INTENT_BEGIN, INTENT_END) or INTENT_PLACEHOLDER


def write_facts(project_root: Path, facts_md: str) -> None:
    """Replace the facts half in place, leaving the intent half untouched."""
    path = ensure_state_file(project_root)
    text = path.read_text(encoding="utf-8")
    start = text.find(FACTS_BEGIN) + len(FACTS_BEGIN)
    stop = text.find(FACTS_END)
    path.write_text(
        text[:start] + "\n" + facts_md.strip() + "\n" + text[stop:], encoding="utf-8"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_state.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add .claude/hooks/lib/state.py tests/test_state.py
git commit -m "feat: add STATE.md read/write/repair with facts-intent split"
```

---

### Task 4: Deterministic facts collector

**Files:**
- Create: `.claude/hooks/lib/facts.py`
- Test: `tests/test_facts.py`

**Interfaces:**
- Consumes: nothing
- Produces: `collect_facts(project_root: Path, blocks: dict) -> dict[str, str]` — returns a mapping of block name to markdown body, containing only enabled blocks that produced content. Possible keys: `"data_schema"`, `"artifacts"`, `"git"`, `"memory_index"`.

Notes for the implementer: this module is stdlib-only — read the CSV header with plain file I/O, not pandas. `git` is invoked via `subprocess` with a 5-second timeout and its block is omitted entirely when the directory is not a repo.

- [ ] **Step 1: Write the failing test**

Create `tests/test_facts.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".claude" / "hooks"))

from lib.facts import collect_facts

ALL_ON = {"data_schema": True, "artifacts": True, "git": True, "memory_index": True}


def _make_csv(tmp_path, name="data.csv", rows=2):
    lines = ["City,Country,GHI_kWh_per_m2"]
    lines += [f"City{i},Land,4.{i}" for i in range(rows)]
    (tmp_path / name).write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_empty_project_returns_no_blocks(tmp_path):
    assert collect_facts(tmp_path, ALL_ON) == {}


def test_data_schema_reports_columns_and_row_count(tmp_path):
    _make_csv(tmp_path, rows=3)
    block = collect_facts(tmp_path, ALL_ON)["data_schema"]
    assert "data.csv" in block
    assert "3 rows" in block
    assert "GHI_kWh_per_m2" in block


def test_disabled_block_is_omitted(tmp_path):
    _make_csv(tmp_path)
    blocks = dict(ALL_ON, data_schema=False)
    assert "data_schema" not in collect_facts(tmp_path, blocks)


def test_artifacts_lists_analysis_and_output_files(tmp_path):
    (tmp_path / "analysis").mkdir()
    (tmp_path / "analysis" / "roi.py").write_text("", encoding="utf-8")
    (tmp_path / "output").mkdir()
    (tmp_path / "output" / "roi.png").write_text("", encoding="utf-8")
    block = collect_facts(tmp_path, ALL_ON)["artifacts"]
    assert "analysis/roi.py" in block
    assert "output/roi.png" in block


def test_memory_index_lists_paths_with_descriptions(tmp_path):
    mem = tmp_path / "docs" / "memory"
    mem.mkdir(parents=True)
    (mem / "roi-method.md").write_text(
        "# ROI methodology\n\nlong body text\n", encoding="utf-8"
    )
    block = collect_facts(tmp_path, ALL_ON)["memory_index"]
    assert "docs/memory/roi-method.md" in block
    assert "ROI methodology" in block
    assert "long body text" not in block


def test_git_block_absent_when_not_a_repo(tmp_path):
    _make_csv(tmp_path)
    assert "git" not in collect_facts(tmp_path, ALL_ON)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_facts.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lib.facts'`

- [ ] **Step 3: Write the implementation**

Create `.claude/hooks/lib/facts.py`:

```python
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
    lines: list[str] = []
    for name in ARTIFACT_DIRS:
        directory = root / name
        if not directory.is_dir():
            continue
        files = sorted(p for p in directory.rglob("*") if p.is_file())
        for path in files[:MAX_FILES_SHOWN]:
            lines.append(f"- {path.relative_to(root).as_posix()}")
        if len(files) > MAX_FILES_SHOWN:
            lines.append(f"- (+{len(files) - MAX_FILES_SHOWN} more in {name}/)")
    return "\n".join(lines) if lines else None


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
                return stripped.lstrip("# ").strip()
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_facts.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add .claude/hooks/lib/facts.py tests/test_facts.py
git commit -m "feat: add deterministic facts collector"
```

---

### Task 5: Token log

**Files:**
- Create: `.claude/hooks/lib/tokenlog.py`
- Test: `tests/test_tokenlog.py`

**Interfaces:**
- Consumes: nothing
- Produces: `append_entry(project_root: Path, tokens: int, blocks: list[str]) -> None`

- [ ] **Step 1: Write the failing test**

Create `tests/test_tokenlog.py`:

```python
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".claude" / "hooks"))

from lib.tokenlog import append_entry, log_path


def test_append_creates_file_and_writes_one_json_line(tmp_path):
    append_entry(tmp_path, 512, ["data_schema", "intent"])
    lines = log_path(tmp_path).read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["tokens"] == 512
    assert entry["blocks"] == ["data_schema", "intent"]
    assert "timestamp" in entry


def test_append_is_additive(tmp_path):
    append_entry(tmp_path, 100, ["intent"])
    append_entry(tmp_path, 200, ["intent"])
    lines = log_path(tmp_path).read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2


def test_append_never_raises_on_unwritable_path(tmp_path):
    blocker = tmp_path / "docs"
    blocker.write_text("I am a file, not a directory", encoding="utf-8")
    append_entry(tmp_path, 100, ["intent"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tokenlog.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lib.tokenlog'`

- [ ] **Step 3: Write the implementation**

Create `.claude/hooks/lib/tokenlog.py`:

```python
"""Append-only record of what each injection cost, so the harness is measurable."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def log_path(project_root: Path) -> Path:
    return Path(project_root) / "docs" / "token_log.jsonl"


def append_entry(project_root: Path, tokens: int, blocks: list[str]) -> None:
    """Append one JSON line. Silently does nothing if the log cannot be written."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tokens": tokens,
        "blocks": blocks,
    }
    try:
        path = log_path(project_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
    except (OSError, ValueError):
        return
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_tokenlog.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add .claude/hooks/lib/tokenlog.py tests/test_tokenlog.py
git commit -m "feat: add token usage log"
```

---

### Task 6: SessionStart injection hook

**Files:**
- Create: `.claude/hooks/inject_context.py`
- Create: `.claude/settings.json`
- Test: `tests/test_inject_context.py`

**Interfaces:**
- Consumes: `load_config` (Task 1), `estimate_tokens`/`truncate_to_budget` (Task 2), `read_intent`/`write_facts` (Task 3), `collect_facts` (Task 4), `append_entry` (Task 5)
- Produces: `build_block(project_root: Path, config: dict) -> tuple[str, list[str]]` and a `main()` that reads hook JSON on stdin and prints the hook response on stdout

Block assembly order: `data_schema`, `artifacts`, `git` (sharing the `facts` budget), then `memory_index` (own budget), then `intent` (own budget). The assembled block is then truncated to the `total` budget as a final hard cap.

- [ ] **Step 1: Write the failing test**

Create `tests/test_inject_context.py`:

```python
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / ".claude" / "hooks" / "inject_context.py"
sys.path.insert(0, str(REPO / ".claude" / "hooks"))

from lib.config import DEFAULT_CONFIG
from lib.state import read_intent, state_path


def run_hook(cwd: Path, payload: dict | None = None):
    payload = payload or {"hook_event_name": "SessionStart", "cwd": str(cwd)}
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(cwd),
        timeout=30,
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_inject_context.py -v`
Expected: FAIL — the hook file does not exist

- [ ] **Step 3: Write the implementation**

Create `.claude/hooks/inject_context.py`:

```python
"""SessionStart hook: build and inject the compact project state block.

Fails open. Any exception results in no output and exit code 0.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.budget import estimate_tokens, truncate_to_budget
from lib.config import load_config
from lib.facts import collect_facts
from lib.state import read_intent, write_facts
from lib.tokenlog import append_entry

FACTS_ORDER = ("data_schema", "artifacts", "git")
HEADINGS = {
    "data_schema": "Data",
    "artifacts": "Artifacts",
    "git": "Git",
    "memory_index": "Memory notes (read only if relevant)",
    "intent": "Where we left off",
}


def _resolve_root(payload: dict) -> Path:
    for candidate in (payload.get("cwd"), os.environ.get("CLAUDE_PROJECT_DIR")):
        if candidate:
            return Path(candidate)
    return Path.cwd()


def _section(name: str, body: str) -> str:
    return f"### {HEADINGS[name]}\n{body}"


def build_block(project_root: Path, config: dict) -> tuple[str, list[str]]:
    """Return (block_markdown, included_block_names)."""
    blocks = config.get("blocks", {})
    budget = config.get("token_budget", {})
    facts = collect_facts(project_root, blocks)
    included: list[str] = []
    parts: list[str] = []

    facts_md = "\n\n".join(
        _section(name, facts[name]) for name in FACTS_ORDER if name in facts
    )
    if facts_md:
        parts.append(truncate_to_budget(facts_md, budget.get("facts", 400)))
        included.extend(name for name in FACTS_ORDER if name in facts)

    if "memory_index" in facts:
        parts.append(
            truncate_to_budget(
                _section("memory_index", facts["memory_index"]),
                budget.get("memory_index", 100),
            )
        )
        included.append("memory_index")

    if blocks.get("intent", True):
        intent = read_intent(project_root)
        parts.append(
            truncate_to_budget(_section("intent", intent), budget.get("intent", 300))
        )
        included.append("intent")

    # Persist the facts half so the on-disk file stays true.
    write_facts(project_root, facts_md or "(no facts collected)")

    if not parts:
        return "", included
    header = "## Project state (auto-injected, read-only)"
    block = header + "\n\n" + "\n\n".join(p for p in parts if p)
    return truncate_to_budget(block, budget.get("total", 800)), included


def main() -> None:
    try:
        raw = sys.stdin.read()
    except OSError:
        raw = ""
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except ValueError:
        payload = {}

    root = _resolve_root(payload)
    config = load_config(root)
    block, included = build_block(root, config)

    if config.get("token_logging", True) and block:
        append_entry(root, estimate_tokens(block), included)

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": block,
        }
    }))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_inject_context.py -v`
Expected: 8 passed

- [ ] **Step 5: Wire the hook into settings**

Create `.claude/settings.json`:

```json
{
  "model": "opus",
  "effortLevel": "high",
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python \"$CLAUDE_PROJECT_DIR/.claude/hooks/inject_context.py\"",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 6: Verify the hook runs live**

Run: `claude --debug -p "reply with only the word ready"`
Expected: debug output shows `inject_context.py` executing and the state block being added. Confirm a new line appended to `docs/token_log.jsonl`.

- [ ] **Step 7: Commit**

```bash
git add .claude/hooks/inject_context.py .claude/settings.json tests/test_inject_context.py docs/STATE.md
git commit -m "feat: add SessionStart context injection hook"
```

---

### Task 7: Stop checkpoint gate

**Files:**
- Create: `.claude/hooks/checkpoint_gate.py`
- Modify: `.claude/settings.json` (add the `Stop` entry alongside `SessionStart`)
- Test: `tests/test_checkpoint_gate.py`

**Interfaces:**
- Consumes: `load_config` (Task 1), `state_path` (Task 3)
- Produces: `needs_checkpoint(project_root: Path) -> bool`, `main()`

Logic: return `True` when any file under `analysis/`, `output/`, or `docs/memory/` has an mtime newer than `docs/STATE.md`. When `True` and `stop_hook_active` is falsy, emit a block decision asking the model to record intent. Otherwise print nothing and exit 0.

- [ ] **Step 1: Write the failing test**

Create `tests/test_checkpoint_gate.py`:

```python
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
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(cwd),
        timeout=30,
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_checkpoint_gate.py -v`
Expected: FAIL — the hook file does not exist

- [ ] **Step 3: Write the implementation**

Create `.claude/hooks/checkpoint_gate.py`:

```python
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
    for candidate in (payload.get("cwd"), os.environ.get("CLAUDE_PROJECT_DIR")):
        if candidate:
            return Path(candidate)
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_checkpoint_gate.py -v`
Expected: 5 passed

- [ ] **Step 5: Add the Stop hook to settings**

In `.claude/settings.json`, add a `"Stop"` key inside `"hooks"`, as a sibling of `"SessionStart"`:

```json
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python \"$CLAUDE_PROJECT_DIR/.claude/hooks/checkpoint_gate.py\"",
            "timeout": 10
          }
        ]
      }
    ]
```

- [ ] **Step 6: Commit**

```bash
git add .claude/hooks/checkpoint_gate.py .claude/settings.json tests/test_checkpoint_gate.py
git commit -m "feat: add Stop checkpoint gate for intent recording"
```

---

### Task 8: PreCompact preservation

**Files:**
- Create: `.claude/hooks/preserve_compact.py`
- Modify: `.claude/settings.json` (add the `PreCompact` entry)
- Test: `tests/test_preserve_compact.py`

**Interfaces:**
- Consumes: `read_intent` (Task 3)
- Produces: `main()`, plus the note file `docs/memory/pre-compact-<UTC timestamp>.md`

- [ ] **Step 1: Write the failing test**

Create `tests/test_preserve_compact.py`:

```python
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / ".claude" / "hooks" / "preserve_compact.py"
sys.path.insert(0, str(REPO / ".claude" / "hooks"))

from lib.state import ensure_state_file, state_path


def run_hook(cwd: Path):
    payload = {"hook_event_name": "PreCompact", "cwd": str(cwd), "trigger": "auto"}
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(cwd),
        timeout=30,
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
    notes = list((tmp_path / "docs" / "memory").glob("pre-compact-*.md"))
    assert len(notes) == 1
    assert "finish ROI chart" in notes[0].read_text(encoding="utf-8")


def test_emits_preservation_instruction(tmp_path):
    _seed_intent(tmp_path)
    result = run_hook(tmp_path)
    assert "STATE.md" in result.stdout


def test_exits_zero_on_empty_project(tmp_path):
    result = run_hook(tmp_path)
    assert result.returncode == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_preserve_compact.py -v`
Expected: FAIL — the hook file does not exist

- [ ] **Step 3: Write the implementation**

Create `.claude/hooks/preserve_compact.py`:

```python
"""PreCompact hook: persist intent to a memory note before the window resets."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.state import read_intent

INSTRUCTION = (
    "When summarizing, preserve the injected project state block verbatim and keep "
    "the intent recorded in docs/STATE.md. Prior intent was also saved to "
    "docs/memory/ as a pre-compact note."
)


def _resolve_root(payload: dict) -> Path:
    for candidate in (payload.get("cwd"), os.environ.get("CLAUDE_PROJECT_DIR")):
        if candidate:
            return Path(candidate)
    return Path.cwd()


def main() -> None:
    try:
        raw = sys.stdin.read()
    except OSError:
        raw = ""
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except ValueError:
        payload = {}

    root = _resolve_root(payload)
    intent = read_intent(root)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    note = root / "docs" / "memory" / f"pre-compact-{stamp}.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(
        f"# Pre-compact snapshot {stamp}\n\n"
        f"Trigger: {payload.get('trigger', 'unknown')}\n\n"
        f"## Intent at compaction\n\n{intent}\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreCompact",
            "additionalContext": INSTRUCTION,
        }
    }))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_preserve_compact.py -v`
Expected: 3 passed

- [ ] **Step 5: Add the PreCompact hook to settings**

In `.claude/settings.json`, add inside `"hooks"`:

```json
    "PreCompact": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python \"$CLAUDE_PROJECT_DIR/.claude/hooks/preserve_compact.py\"",
            "timeout": 10
          }
        ]
      }
    ]
```

- [ ] **Step 6: Run the full test suite**

Run: `python -m pytest tests/ -v`
Expected: 39 passed

- [ ] **Step 7: Commit**

```bash
git add .claude/hooks/preserve_compact.py .claude/settings.json tests/test_preserve_compact.py
git commit -m "feat: add PreCompact intent preservation"
```

---

### Task 9: Sonnet worker agents

**Files:**
- Create: `.claude/agents/data-profiler.md`
- Create: `.claude/agents/chart-builder.md`
- Create: `.claude/agents/doc-writer.md`
- Create: `.claude/agents/verifier.md`

**Interfaces:**
- Consumes: nothing
- Produces: four agent types invokable by name via the Agent tool

Each agent uses `model: sonnet`, a narrow tool allowlist, and an explicit digest-only return contract. The digest requirement is where the token saving comes from — an agent that returns its whole transcript saves nothing.

- [ ] **Step 1: Create `data-profiler`**

```markdown
---
name: data-profiler
description: Use for pandas profiling of the solar dataset — describes, null and outlier scans, group-bys, correlation checks. Returns a compact numeric digest, never a transcript.
model: sonnet
tools: Read, Write, Bash, Glob, Grep
---

You profile tabular data and report findings compactly.

## Process
1. Read the CSV with pandas.
2. Run exactly the analysis you were asked for. Do not expand scope.
3. Write any throwaway script to the scratchpad, not the project.

## Return contract
Return **under 300 tokens**: the numeric findings as a small markdown table or
tight bullets, plus one line naming anything that looks wrong with the data.

Never return raw pandas output, full dataframes, or a narrative of your steps.
Round floats to 2 decimals. If a result is ambiguous, say so in one clause
rather than speculating — interpretation is the caller's job.
```

- [ ] **Step 2: Create `chart-builder`**

```markdown
---
name: chart-builder
description: Use to build one chart to an explicit spec — writes the plotting script, runs it, confirms the output file exists. Returns the file path only.
model: sonnet
tools: Read, Write, Edit, Bash, Glob
---

You build exactly one chart per invocation, to the spec you were given.

## Process
1. Write the script to `analysis/charts/<name>.py`.
2. Save output to `output/<name>.png` at dpi=150 with `bbox_inches="tight"`.
3. Run the script. If it errors, fix and rerun — up to 3 attempts.
4. Verify the output file exists and is non-empty before reporting success.

## Requirements
- Label both axes with units. Title states the finding, not the chart type.
- No chartjunk: no 3D, no gradients, no unexplained double axes.
- Do not invent styling decisions the spec did not ask for.

## Return contract
Return **under 100 tokens**: the script path, the image path, and confirmation
the file exists with its size. If you failed after 3 attempts, return the final
error message verbatim and stop — do not redesign the chart to dodge the error.
```

- [ ] **Step 3: Create `doc-writer`**

```markdown
---
name: doc-writer
description: Use to draft README sections, docstrings, or memory-note formatting from facts you supply. Returns prose only.
model: sonnet
tools: Read, Write, Edit, Glob, Grep
---

You write short technical prose from facts the caller supplies.

## Rules
- Use only facts given to you or read from files. Never invent numbers,
  findings, or results.
- Plain declarative sentences. No marketing tone, no "delve", no "leverage".
- Memory notes start with a `# One-line title` — the facts collector uses that
  first line as the note's description in the injected index, so make it
  specific and self-contained.

## Return contract
Return the requested text only, under 400 tokens unless told otherwise. No
preamble, no explanation of your choices. If a fact you need is missing, list
exactly what is missing in one line instead of guessing.
```

- [ ] **Step 4: Create `verifier`**

```markdown
---
name: verifier
description: Use to run tests, scripts, or the hook suite and report pass/fail. Returns a verdict plus failing output only.
model: sonnet
tools: Read, Bash, Glob, Grep
---

You run things and report what happened. You do not fix anything.

## Process
1. Run the exact command you were given.
2. Capture the real exit code and output.

## Return contract
Return **under 200 tokens**:
- Line 1: `PASS` or `FAIL` plus counts (e.g. `FAIL — 33 passed, 2 failed`).
- Then, only for failures: the test name and the assertion or traceback line
  that actually failed.

Never report a pass you did not observe. Never truncate a failure into
vagueness — the failing line is the whole point. Never edit code to make a
test pass; report and stop.
```

- [ ] **Step 5: Verify the agents load**

Run: `claude --debug -p "list your available agent types"`
Expected: all four names appear. If not, check the frontmatter parses as valid YAML.

- [ ] **Step 6: Commit**

```bash
git add .claude/agents/
git commit -m "feat: add four Sonnet worker agents"
```

---

### Task 10: CLAUDE.md response contract and routing policy

**Files:**
- Create: `CLAUDE.md`

**Interfaces:**
- Consumes: the four agent names from Task 9, the `verbosity` and `delegation` keys from Task 1
- Produces: the always-loaded instruction layer

Keep this file under 60 lines. It is loaded on every single session, so every line spends tokens forever — that constraint is the whole point of the harness.

- [ ] **Step 1: Write the file**

```markdown
# Solar Energy Worldwide Analysis

Analysis of `solar_energy_worldwide.csv` (48 cities, 17 columns) producing
viability scoring, ROI comparison, regional breakdowns, and a dashboard.

## Response contract

- Answer first. No preamble, no restating the question, no "great question".
- Findings as tight bullets or a small table. Prose only when reasoning matters.
- Code without narration. Explain a line only if it is genuinely non-obvious.
- State uncertainty in one clause, not a paragraph. Never pad to sound thorough.
- Report what happened, not what should have happened. If a test failed, say so
  and show the failing output.

Verbosity follows `verbosity` in `.claude/context.config.json`:
`lean` (default) = minimum that fully answers; `normal` = add brief rationale;
`explain` = walk through reasoning. Read the config if unsure which is active.

## Model routing

Main thread is Opus 5 at high effort: planning, architecture, debugging,
interpreting ambiguous results, deciding approach.

Delegate to Sonnet workers when the task is mechanical, fully specified, and
verifiable without judgment:

| Agent | Delegate for |
|---|---|
| `data-profiler` | describes, null/outlier scans, group-bys, correlations |
| `chart-builder` | building one chart to an explicit spec |
| `doc-writer` | README sections, docstrings, memory notes |
| `verifier` | running tests or scripts and reporting pass/fail |

Do **not** delegate: choosing an approach, interpreting an ambiguous result,
debugging, or anything where you would have to guess what the user wants.

**Anti-rule:** never delegate work smaller than the spawn cost. Single-file
reads, one-line edits, and quick greps stay on the main thread.

Set `delegation.enabled` to `false` in the config to suspend delegation.

## Context system

- `docs/STATE.md` — auto-injected at session start. The facts half is
  script-owned; never hand-edit it. The intent half is yours to update.
- `docs/memory/*.md` — deeper notes. The injected block lists paths and
  one-line descriptions only. Read a note when the task touches it, not
  preemptively.
- `docs/DECISIONS.md` — append-only. Record a decision here when you choose
  between real alternatives, with the reason.
- `docs/token_log.jsonl` — what each injection cost. Check it if the harness
  feels expensive.

## Project layout

- `analysis/` — analysis scripts; `analysis/charts/` for plotting scripts
- `output/` — generated charts and the dashboard
- `.claude/hooks/` — harness hooks, stdlib-only, must fail open
- `tests/` — pytest suite for the hooks

Run tests with `python -m pytest tests/ -v`.
```

- [ ] **Step 2: Create the decisions log**

Create `docs/DECISIONS.md`:

```markdown
# Decisions

Append-only. Newest last. One entry per real choice between alternatives.

## 2026-08-12 — Context harness architecture

Chose script-written facts plus model-written intent, injected once per session
at `SessionStart`. Rejected per-prompt `UserPromptSubmit` injection: it blocks
every turn and re-spends tokens each time, which defeats the purpose.

Chose mtime comparison over transcript parsing for the checkpoint gate —
deterministic and independent of transcript format.
```

- [ ] **Step 3: Verify the full system end to end**

Run: `python -m pytest tests/ -v`
Expected: 39 passed

Run: `claude --debug -p "What is in the injected state block? Quote it."`
Expected: the block includes the CSV schema, the memory index, and the intent
section, and its length is at or under the 800-token budget.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md docs/DECISIONS.md docs/STATE.md
git commit -m "feat: add response contract, routing policy, and decisions log"
```

---

## Post-implementation check

After Task 10, review `docs/token_log.jsonl` across a few real sessions. If the
injected block is consistently near 800 tokens but you rarely act on the facts
half, cut `token_budget.facts` or disable individual blocks. The kill switch is
setting every entry in `blocks` to `false` — no hook edits needed.

## Self-review notes

Spec coverage verified against `docs/superpowers/specs/2026-08-12-context-management-design.md`:

| Spec requirement | Task |
|---|---|
| `context.config.json` + defaults fallback | 1 |
| Token budgets and hard cap | 2, 6 |
| `STATE.md` facts/intent split, template repair | 3 |
| Facts: CSV schema, artifacts, git, memory index | 4 |
| `token_log.jsonl` | 5 |
| SessionStart injection, `additionalContext`, budget truncation | 6 |
| Stop checkpoint gate with loop guard | 7 |
| PreCompact preservation | 8 |
| Four Sonnet agents with digest contracts | 9 |
| Response contract, routing policy, anti-rule | 10 |
| `effortLevel: high` in project settings | 6 (settings.json) |
| Hooks fail open | every hook: `try/except` in `__main__` |
| Test fixtures: empty, populated, malformed STATE, missing config, oversized index | 6 |
| Kill switch | 1 (config), verified in 6 |
