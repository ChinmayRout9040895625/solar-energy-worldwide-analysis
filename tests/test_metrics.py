import math
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.metrics import (
    PAYBACK_LOW_MAX,
    PAYBACK_MEDIUM_MAX,
    payback_band_counts,
    payback_risk_band,
)

CSV = Path(__file__).resolve().parents[1] / "solar_energy_worldwide.csv"


@pytest.fixture(scope="module")
def real() -> pd.DataFrame:
    return pd.read_csv(CSV)


def test_band_below_low_max_is_low():
    assert payback_risk_band(5.8) == "Low"
    assert payback_risk_band(6.999) == "Low"


def test_exact_low_boundary_is_medium_not_low():
    # No real row sits on 7.0, so this boundary is only reachable synthetically.
    assert payback_risk_band(PAYBACK_LOW_MAX) == "Medium"


def test_exact_medium_upper_boundary_is_medium_not_high():
    assert payback_risk_band(PAYBACK_MEDIUM_MAX) == "Medium"


def test_just_above_medium_max_is_high():
    assert payback_risk_band(9.0001) == "High"
    assert payback_risk_band(15.3) == "High"


def test_band_counts_match_real_distribution(real):
    assert payback_band_counts(real) == {"Low": 5, "Medium": 19, "High": 24}


def test_band_counts_sum_to_row_count(real):
    assert sum(payback_band_counts(real).values()) == len(real)


def test_band_counts_always_include_all_three_keys():
    synthetic = pd.DataFrame({"Payback_Period_Years": [6.0, 6.5]})
    assert payback_band_counts(synthetic) == {"Low": 2, "Medium": 0, "High": 0}


from analysis.metrics import regional_mean_roi, regional_roi_rank


def test_rank_matches_verified_order(real):
    assert regional_roi_rank(real) == {
        "Middle East": 1,
        "Africa": 2,
        "Oceania": 3,
        "North America": 4,
        "Asia": 5,
        "South America": 6,
        "Europe": 7,
    }


def test_mean_roi_matches_verified_values(real):
    means = regional_mean_roi(real)
    assert math.isclose(means["Middle East"], 14.5, abs_tol=1e-9)
    assert math.isclose(means["Africa"], 14.266666666666667, abs_tol=1e-9)
    assert math.isclose(means["Europe"], 8.85, abs_tol=1e-9)


def test_rank_covers_every_region_exactly_once(real):
    ranks = regional_roi_rank(real)
    assert len(ranks) == real["Region"].nunique() == 7
    assert sorted(ranks.values()) == [1, 2, 3, 4, 5, 6, 7]


def test_dense_rank_shares_rank_on_tie_without_skipping():
    synthetic = pd.DataFrame(
        {
            "Region": ["A", "B", "C"],
            "ROI_Percentage": [10.0, 10.0, 5.0],
        }
    )
    ranks = regional_roi_rank(synthetic)
    assert ranks["A"] == 1
    assert ranks["B"] == 1
    assert ranks["C"] == 2  # dense: no gap after the tie


from analysis.metrics import (
    MIN_CITIES_FOR_CONSISTENCY,
    SMALL_SAMPLE_MAX,
    cities_per_region,
    production_consistency,
    small_sample_regions,
)


def test_consistency_matches_verified_values(real):
    cons = production_consistency(real)
    assert math.isclose(cons["Africa"], 0.9343, abs_tol=5e-5)
    assert math.isclose(cons["Asia"], 0.8264, abs_tol=5e-5)
    assert math.isclose(cons["Europe"], 0.7454, abs_tol=5e-5)
    assert math.isclose(cons["North America"], 0.7616, abs_tol=5e-5)
    assert math.isclose(cons["Oceania"], 0.9020, abs_tol=5e-5)
    assert math.isclose(cons["South America"], 0.8412, abs_tol=5e-5)


def test_single_city_region_is_none_not_one(real):
    # Middle East has exactly one city. Zero variance must not read as
    # perfect consistency.
    assert production_consistency(real)["Middle East"] is None


def test_every_region_appears_in_consistency(real):
    assert set(production_consistency(real)) == set(real["Region"].unique())


def test_two_city_region_is_none():
    synthetic = pd.DataFrame(
        {
            "Region": ["A", "A"],
            "Avg_Annual_Production_kWh": [10000, 12000],
        }
    )
    assert production_consistency(synthetic)["A"] is None


def test_three_city_region_is_computed():
    synthetic = pd.DataFrame(
        {
            "Region": ["A", "A", "A"],
            "Avg_Annual_Production_kWh": [10000, 10000, 10000],
        }
    )
    # Zero spread across 3 cities is genuine perfect consistency.
    assert production_consistency(synthetic)["A"] == 1.0


def test_consistency_is_clamped_to_zero_floor():
    # Extreme spread drives 1 - cv negative; it must clamp, not go below 0.
    synthetic = pd.DataFrame(
        {
            "Region": ["A", "A", "A"],
            "Avg_Annual_Production_kWh": [1, 1, 100000],
        }
    )
    assert production_consistency(synthetic)["A"] == 0.0


def test_small_sample_regions_match_real_data(real):
    assert small_sample_regions(real) == {"Africa", "Oceania", "Middle East"}


def test_cities_per_region_matches_real_data(real):
    assert cities_per_region(real) == {
        "Europe": 16,
        "Asia": 12,
        "North America": 8,
        "South America": 5,
        "Oceania": 3,
        "Africa": 3,
        "Middle East": 1,
    }


def test_threshold_constants_are_ordered():
    assert MIN_CITIES_FOR_CONSISTENCY < SMALL_SAMPLE_MAX
