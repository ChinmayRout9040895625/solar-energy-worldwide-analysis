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
    correlations,
    main,
    reconcile,
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
        "correlations",
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


def test_payload_caveats_state_the_specific_verified_facts(real):
    joined = " ".join(build_payload(real)["caveats"])
    lowered = joined.lower()
    # The two constant columns, with their actual constant values.
    assert "Electricity_Price_USD_per_kWh is constant at 0.15" in joined
    assert real["Electricity_Price_USD_per_kWh"].nunique() == 1
    assert float(real["Electricity_Price_USD_per_kWh"].iloc[0]) == 0.15
    assert "Avg_System_Cost_USD is constant at 15000" in joined
    assert real["Avg_System_Cost_USD"].nunique() == 1
    assert int(real["Avg_System_Cost_USD"].iloc[0]) == 15000
    # Payback is a ROUNDED ratio, not an exact function (see F6).
    assert "rounded to one decimal place" in lowered
    assert "exact" in lowered
    # The UAE / Asia classification, preserved not recoded.
    assert "Region=Asia while Country=UAE" in joined
    assert (
        real.loc[real["City"] == "Dubai", "Region"].iloc[0] == "Asia"
    )
    assert real.loc[real["City"] == "Dubai", "Country"].iloc[0] == "UAE"
    # Sample size and the small-region counts.
    assert "48 cities in 30 countries" in joined
    assert len(real) == 48 and real["Country"].nunique() == 30
    assert "Middle East (1 city), Africa (3) and Oceania (3)" in joined
    counts = real["Region"].value_counts().to_dict()
    assert counts["Middle East"] == 1
    assert counts["Africa"] == 3
    assert counts["Oceania"] == 3


def test_correlations_match_the_spec_values(real):
    c = build_payload(real)["correlations"]
    assert c == {
        "installations_vs_roi": 0.137,
        "roi_vs_viability": 0.982,
        "ghi_vs_production": 0.979,
    }


def test_caveat_quotes_the_computed_correlation(real):
    payload = build_payload(real)
    value = payload["correlations"]["installations_vs_roi"]
    matching = [c for c in payload["caveats"] if str(value) in c]
    assert matching, f"no caveat mentions the computed correlation {value}"
    assert "ROI_Percentage" in matching[0]


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


def test_duplicate_city_row_is_rejected_by_name(real):
    broken = pd.concat([real, real.iloc[[0]]], ignore_index=True)
    with pytest.raises(DataValidationError) as excinfo:
        validate(broken)
    message = str(excinfo.value)
    assert "duplicate" in message.lower()
    assert str(real.iloc[0]["City"]) in message


def test_multi_region_country_is_rejected_with_country_and_regions_named(real):
    broken = real.copy()
    target = broken.loc[broken["Country"] == "Germany"].index
    assert len(target) >= 2, "test needs a multi-city country"
    broken.loc[target[0], "Region"] = "Africa"
    with pytest.raises(DataValidationError) as excinfo:
        validate(broken)
    message = str(excinfo.value)
    assert "Germany" in message
    assert "Africa" in message
    assert "Europe" in message


def test_object_dtype_numeric_column_is_rejected_by_name(real):
    broken = real.copy()
    broken["Solar_Installations_Count"] = broken[
        "Solar_Installations_Count"
    ].astype(str)
    with pytest.raises(DataValidationError) as excinfo:
        validate(broken)
    message = str(excinfo.value)
    assert "Solar_Installations_Count" in message
    assert "numeric" in message.lower()


# --- reconcile's numeric branches (F3): each perturbation must abort ---


def _payload(real):
    return build_payload(real)


def test_reconcile_detects_corrupt_region_co2(real):
    payload = _payload(real)
    payload["regions"][0]["co2_tons"] += 5.0
    with pytest.raises(DataValidationError) as excinfo:
        reconcile(real, payload)
    message = str(excinfo.value)
    assert "regions" in message
    assert "co2_tons" in message


def test_reconcile_detects_corrupt_country_installations(real):
    payload = _payload(real)
    payload["countries"][0]["installations"] += 1
    with pytest.raises(DataValidationError) as excinfo:
        reconcile(real, payload)
    message = str(excinfo.value)
    assert "countries" in message
    assert "installations" in message


def test_reconcile_detects_corrupt_region_production(real):
    payload = _payload(real)
    payload["regions"][0]["production_kwh"] += 100
    with pytest.raises(DataValidationError) as excinfo:
        reconcile(real, payload)
    message = str(excinfo.value)
    assert "regions" in message
    assert "production_kwh" in message


def test_reconcile_detects_corrupt_totals_installations(real):
    payload = _payload(real)
    payload["totals"]["installations"] += 1
    with pytest.raises(DataValidationError) as excinfo:
        reconcile(real, payload)
    message = str(excinfo.value)
    assert "totals" in message
    assert "installations" in message


def test_reconcile_detects_corrupt_totals_co2(real):
    payload = _payload(real)
    payload["totals"]["co2_tons"] += 1.0
    with pytest.raises(DataValidationError) as excinfo:
        reconcile(real, payload)
    message = str(excinfo.value)
    assert "totals" in message
    assert "co2_tons" in message


def test_reconcile_detects_corrupt_city_co2(real):
    payload = _payload(real)
    payload["cities"][0]["co2_tons"] += 1.0
    with pytest.raises(DataValidationError) as excinfo:
        reconcile(real, payload)
    message = str(excinfo.value)
    assert "cities" in message
    assert "co2_tons" in message


def test_reconcile_detects_corrupt_city_installations(real):
    payload = _payload(real)
    payload["cities"][0]["installations"] += 1
    with pytest.raises(DataValidationError) as excinfo:
        reconcile(real, payload)
    message = str(excinfo.value)
    assert "cities" in message
    assert "installations" in message


def test_reconcile_detects_a_dropped_and_duplicated_city(real):
    """Count stays at 48, so only value reconciliation catches this."""
    payload = _payload(real)
    payload["cities"][1] = dict(payload["cities"][0])
    with pytest.raises(DataValidationError) as excinfo:
        reconcile(real, payload)
    assert "cities" in str(excinfo.value)


def test_reconcile_detects_corrupt_region_risk_counts(real):
    payload = _payload(real)
    payload["regions"][0]["risk_counts"]["Low"] += 1
    with pytest.raises(DataValidationError) as excinfo:
        reconcile(real, payload)
    message = str(excinfo.value)
    assert "regions" in message
    assert "risk_counts" in message


def test_reconcile_detects_corrupt_country_city_count(real):
    payload = _payload(real)
    payload["countries"][0]["cities"] += 1
    with pytest.raises(DataValidationError) as excinfo:
        reconcile(real, payload)
    message = str(excinfo.value)
    assert "countries" in message
    assert "cities" in message


def test_reconcile_passes_on_the_real_payload(real):
    reconcile(real, _payload(real))  # must not raise


def test_main_returns_zero_on_success(tmp_path):
    assert main([str(CSV), str(tmp_path / "data.json")]) == 0


def test_main_returns_one_on_validation_failure(tmp_path):
    assert main([str(tmp_path / "absent.csv"), str(tmp_path / "data.json")]) == 1
