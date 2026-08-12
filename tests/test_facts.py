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
