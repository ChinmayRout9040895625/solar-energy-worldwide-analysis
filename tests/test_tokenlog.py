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
