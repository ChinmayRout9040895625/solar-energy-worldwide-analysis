import json
import math
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.build_data import (
    REQUIRED_COLUMNS,
    DataValidationError,
    build,
    build_payload,
    main,
    validate,
)

CSV = Path(__file__).resolve().parents[1] / "solar_energy_worldwide.csv"


@pytest.fixture(scope="module")
def real() -> pd.DataFrame:
    return pd.read_csv(CSV)


def test_real_data_validates(real):
    validate(real)  # must not raise


def test_required_columns_match_the_real_file(real):
    assert set(REQUIRED_COLUMNS) == set(real.columns)
    assert len(REQUIRED_COLUMNS) == 17


def test_missing_column_is_rejected_by_name(real):
    broken = real.drop(columns=["ROI_Percentage"])
    with pytest.raises(DataValidationError) as excinfo:
        validate(broken)
    assert "ROI_Percentage" in str(excinfo.value)


def test_unexpected_column_is_rejected_by_name(real):
    broken = real.copy()
    broken["Surprise_Column"] = 1
    with pytest.raises(DataValidationError) as excinfo:
        validate(broken)
    assert "Surprise_Column" in str(excinfo.value)


def test_null_value_is_rejected_with_column_named(real):
    broken = real.copy()
    broken.loc[0, "ROI_Percentage"] = None
    with pytest.raises(DataValidationError) as excinfo:
        validate(broken)
    assert "ROI_Percentage" in str(excinfo.value)


def test_empty_frame_is_rejected(real):
    with pytest.raises(DataValidationError):
        validate(real.iloc[0:0])


def test_payload_has_expected_top_level_keys(real):
    payload = build_payload(real)
    assert set(payload) == {
        "meta",
        "totals",
        "caveats",
        "cities",
        "regions",
        "countries",
    }


def test_payload_counts(real):
    payload = build_payload(real)
    assert len(payload["cities"]) == 48
    assert len(payload["regions"]) == 7
    assert len(payload["countries"]) == 30


def test_payload_caveats_mention_the_known_limitations(real):
    joined = " ".join(build_payload(real)["caveats"]).lower()
    assert "constant" in joined
    assert "uae" in joined
    assert "48" in joined


def test_payload_is_json_serialisable(real):
    json.dumps(build_payload(real))  # must not raise


def test_build_writes_the_file_and_returns_the_payload(tmp_path, real):
    out = tmp_path / "data.json"
    payload = build(CSV, out)
    assert out.exists()
    on_disk = json.loads(out.read_text(encoding="utf-8"))
    assert on_disk["totals"] == payload["totals"]
    assert len(on_disk["cities"]) == 48


def test_build_creates_missing_parent_directory(tmp_path):
    out = tmp_path / "nested" / "deeper" / "data.json"
    build(CSV, out)
    assert out.exists()


def test_build_raises_on_missing_csv(tmp_path):
    with pytest.raises(DataValidationError) as excinfo:
        build(tmp_path / "absent.csv", tmp_path / "data.json")
    assert "absent.csv" in str(excinfo.value)


def test_reconciliation_failure_is_detected(tmp_path, real, monkeypatch):
    """A rollup that does not sum to the raw total must abort the build.
    This is the check the Power BI reference would have failed on Dubai."""
    import analysis.build_data as bd

    def dropping_city_records(df):
        from analysis.aggregate import city_records as real_records

        return [r for r in real_records(df) if r["city"] != "Dubai"]

    monkeypatch.setattr(bd, "city_records", dropping_city_records)
    with pytest.raises(DataValidationError) as excinfo:
        bd.build(CSV, tmp_path / "data.json")
    assert "cities" in str(excinfo.value).lower()


def test_main_returns_zero_on_success(tmp_path):
    assert main([str(CSV), str(tmp_path / "data.json")]) == 0


def test_main_returns_one_on_validation_failure(tmp_path):
    assert main([str(tmp_path / "absent.csv"), str(tmp_path / "data.json")]) == 1
