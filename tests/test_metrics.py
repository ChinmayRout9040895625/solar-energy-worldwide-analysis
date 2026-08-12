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
