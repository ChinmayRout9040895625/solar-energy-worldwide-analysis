import math
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.aggregate import (
    city_records,
    country_records,
    country_totals_unrounded,
    region_records,
    region_totals_unrounded,
    totals,
)

CSV = Path(__file__).resolve().parents[1] / "solar_energy_worldwide.csv"


@pytest.fixture(scope="module")
def real() -> pd.DataFrame:
    return pd.read_csv(CSV)


def test_totals_match_verified_values(real):
    t = totals(real)
    assert t["cities"] == 48
    assert t["countries"] == 30
    assert t["regions"] == 7
    assert math.isclose(t["co2_tons"], 208.35, abs_tol=0.005)
    assert t["installations"] == 2328540
    assert t["production_kwh"] == 520875


def test_every_city_appears_exactly_once(real):
    records = city_records(real)
    assert len(records) == 48
    assert len({r["city"] for r in records}) == 48


def test_cities_sorted_by_roi_descending(real):
    rois = [r["roi_pct"] for r in city_records(real)]
    assert rois == sorted(rois, reverse=True)


def test_top_three_cities_by_roi(real):
    top = [r["city"] for r in city_records(real)[:3]]
    assert top == ["Phoenix", "Dubai", "Cairo"]


def test_region_co2_reconciles_to_raw_total(real):
    rolled = sum(v["co2_tons"] for v in region_totals_unrounded(real).values())
    assert math.isclose(
        rolled, real["CO2_Reduction_Tons_per_Year"].sum(), abs_tol=1e-9
    )


def test_region_installations_reconcile_to_raw_total(real):
    rolled = sum(r["installations"] for r in region_records(real))
    assert rolled == int(real["Solar_Installations_Count"].sum())


def test_region_production_reconciles_to_raw_total(real):
    rolled = sum(r["production_kwh"] for r in region_records(real))
    assert rolled == int(real["Avg_Annual_Production_kWh"].sum())


def test_region_city_counts_sum_to_48(real):
    assert sum(r["cities"] for r in region_records(real)) == 48


def test_country_co2_reconciles_to_raw_total(real):
    rolled = sum(v["co2_tons"] for v in country_totals_unrounded(real).values())
    assert math.isclose(
        rolled, real["CO2_Reduction_Tons_per_Year"].sum(), abs_tol=1e-9
    )


def test_rounded_co2_stays_within_rounding_bound_of_unrounded_sum(real):
    region_unrounded = region_totals_unrounded(real)
    regions = region_records(real)
    region_bound = len(regions) * 0.005
    assert math.isclose(
        sum(r["co2_tons"] for r in regions),
        sum(v["co2_tons"] for v in region_unrounded.values()),
        abs_tol=region_bound,
    )

    country_unrounded = country_totals_unrounded(real)
    countries = country_records(real)
    country_bound = len(countries) * 0.005
    assert math.isclose(
        sum(r["co2_tons"] for r in countries),
        sum(v["co2_tons"] for v in country_unrounded.values()),
        abs_tol=country_bound,
    )


def test_country_installations_reconcile_to_raw_total(real):
    rolled = sum(r["installations"] for r in country_records(real))
    assert rolled == int(real["Solar_Installations_Count"].sum())


def test_region_co2_matches_verified_per_region_values(real):
    by_region = {r["region"]: r["co2_tons"] for r in region_records(real)}
    assert math.isclose(by_region["Africa"], 17.10, abs_tol=0.005)
    assert math.isclose(by_region["Asia"], 54.72, abs_tol=0.005)
    assert math.isclose(by_region["Europe"], 56.70, abs_tol=0.005)
    assert math.isclose(by_region["Middle East"], 5.76, abs_tol=0.005)
    assert math.isclose(by_region["North America"], 38.43, abs_tol=0.005)
    assert math.isclose(by_region["Oceania"], 14.58, abs_tol=0.005)
    assert math.isclose(by_region["South America"], 21.06, abs_tol=0.005)


def test_regions_sorted_by_rank(real):
    ranks = [r["rank"] for r in region_records(real)]
    assert ranks == sorted(ranks)
    assert region_records(real)[0]["region"] == "Middle East"


def test_middle_east_consistency_is_none_and_flagged_small(real):
    me = next(r for r in region_records(real) if r["region"] == "Middle East")
    assert me["consistency"] is None
    assert me["small_sample"] is True


def test_europe_is_not_small_sample(real):
    eu = next(r for r in region_records(real) if r["region"] == "Europe")
    assert eu["small_sample"] is False
    assert math.isclose(eu["consistency"], 0.75, abs_tol=0.006)


def test_region_risk_counts_sum_to_region_city_count(real):
    for record in region_records(real):
        assert sum(record["risk_counts"].values()) == record["cities"]


def test_risk_counts_across_regions_match_global_distribution(real):
    combined = {"Low": 0, "Medium": 0, "High": 0}
    for record in region_records(real):
        for band, count in record["risk_counts"].items():
            combined[band] += count
    assert combined == {"Low": 5, "Medium": 19, "High": 24}


def test_dubai_present_in_every_rollup(real):
    """Regression guard: the Power BI reference dashboard silently omitted
    Dubai, understating Asia's CO2 by 6.30 and total installations by 850,
    and dropping the second-highest-ROI city from its ranking entirely."""
    cities = city_records(real)
    dubai = next((r for r in cities if r["city"] == "Dubai"), None)
    assert dubai is not None, "Dubai missing from city_records"
    assert dubai["country"] == "UAE"
    assert dubai["region"] == "Asia"
    assert math.isclose(dubai["roi_pct"], 15.9, abs_tol=0.005)
    assert math.isclose(dubai["co2_tons"], 6.3, abs_tol=0.005)
    assert dubai["installations"] == 850
    assert dubai["production_kwh"] == 15750
    assert dubai["risk_band"] == "Low"

    # Dubai is the second-highest ROI city in the dataset.
    assert [r["city"] for r in cities][:2] == ["Phoenix", "Dubai"]

    # Its contribution must be inside the Asia and UAE rollups.
    asia = next(r for r in region_records(real) if r["region"] == "Asia")
    assert math.isclose(asia["co2_tons"], 54.72, abs_tol=0.005), (
        "Asia CO2 is 48.42 without Dubai — the reference's error"
    )
    assert asia["installations"] == 1469100

    uae = next(r for r in country_records(real) if r["country"] == "UAE")
    assert math.isclose(uae["co2_tons"], 6.3, abs_tol=0.005)
    assert uae["installations"] == 850


def test_every_city_record_has_a_risk_band(real):
    assert all(r["risk_band"] in {"Low", "Medium", "High"} for r in city_records(real))


def test_country_records_carry_one_region_each(real):
    # Every country in this dataset sits in exactly one region.
    for record in country_records(real):
        subset = real[real["Country"] == record["country"]]
        assert subset["Region"].nunique() == 1
        assert record["region"] == subset["Region"].iloc[0]
