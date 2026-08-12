"""Region, country, and city rollups as plain JSON-ready dicts.

Every rollup must reconcile to the raw CSV totals; tests/test_aggregate.py
enforces that. Rounding happens only on output — never on values that feed
further arithmetic.
"""

from __future__ import annotations

import pandas as pd

from analysis.metrics import (
    cities_per_region,
    payback_band_counts,
    payback_risk_band,
    production_consistency,
    regional_mean_roi,
    regional_roi_rank,
    small_sample_regions,
)


def _round2(value: float) -> float:
    return round(float(value), 2)


def totals(df: pd.DataFrame) -> dict:
    """Grand totals across the whole dataset."""
    return {
        "cities": int(len(df)),
        "countries": int(df["Country"].nunique()),
        "regions": int(df["Region"].nunique()),
        "co2_tons": _round2(df["CO2_Reduction_Tons_per_Year"].sum()),
        "installations": int(df["Solar_Installations_Count"].sum()),
        "production_kwh": int(df["Avg_Annual_Production_kWh"].sum()),
    }


def city_records(df: pd.DataFrame) -> list[dict]:
    """One record per city, highest ROI first."""
    ordered = df.sort_values(
        ["ROI_Percentage", "City"], ascending=[False, True]
    )
    return [
        {
            "city": str(row.City),
            "country": str(row.Country),
            "region": str(row.Region),
            "lat": float(row.Latitude),
            "lon": float(row.Longitude),
            "ghi": float(row.GHI_kWh_per_m2),
            "sunlight_hours": int(row.Annual_Sunlight_Hours),
            "installations": int(row.Solar_Installations_Count),
            "production_kwh": int(row.Avg_Annual_Production_kWh),
            "savings_usd": _round2(row.Estimated_Annual_Savings_USD),
            "payback_years": _round2(row.Payback_Period_Years),
            "roi_pct": _round2(row.ROI_Percentage),
            "co2_tons": _round2(row.CO2_Reduction_Tons_per_Year),
            "viability": int(row.Solar_Viability_Score),
            "risk_band": payback_risk_band(float(row.Payback_Period_Years)),
        }
        for row in ordered.itertuples(index=False)
    ]


def region_records(df: pd.DataFrame) -> list[dict]:
    """One record per region, best ROI rank first."""
    ranks = regional_roi_rank(df)
    means = regional_mean_roi(df)
    consistency = production_consistency(df)
    small = small_sample_regions(df)
    counts = cities_per_region(df)

    records = []
    for region, group in df.groupby("Region"):
        cons = consistency[str(region)]
        records.append(
            {
                "region": str(region),
                "cities": counts[str(region)],
                "rank": ranks[str(region)],
                "mean_roi": _round2(means[str(region)]),
                "co2_tons": _round2(group["CO2_Reduction_Tons_per_Year"].sum()),
                "installations": int(group["Solar_Installations_Count"].sum()),
                "production_kwh": int(group["Avg_Annual_Production_kWh"].sum()),
                "consistency": None if cons is None else _round2(cons),
                "small_sample": str(region) in small,
                "risk_counts": payback_band_counts(group),
            }
        )
    return sorted(records, key=lambda r: r["rank"])


def country_records(df: pd.DataFrame) -> list[dict]:
    """One record per country, largest CO2 contribution first."""
    records = []
    for country, group in df.groupby("Country"):
        co2_unrounded = float(group["CO2_Reduction_Tons_per_Year"].sum())
        records.append(
            {
                "country": str(country),
                "region": str(group["Region"].iloc[0]),
                "cities": int(len(group)),
                "mean_roi": _round2(group["ROI_Percentage"].mean()),
                "mean_production_kwh": _round2(
                    group["Avg_Annual_Production_kWh"].mean()
                ),
                "co2_tons": _round2(co2_unrounded),
                "installations": int(group["Solar_Installations_Count"].sum()),
                "_co2_unrounded": co2_unrounded,
            }
        )
    records.sort(key=lambda r: (-r["_co2_unrounded"], r["country"]))
    for record in records:
        del record["_co2_unrounded"]
    return records


def region_totals_unrounded(df: pd.DataFrame) -> dict[str, dict[str, float]]:
    """Unrounded per-region group sums, keyed by region name.

    Used for exact reconciliation testing — never round these before
    summing or comparing against the raw CSV totals.
    """
    result: dict[str, dict[str, float]] = {}
    for region, group in df.groupby("Region"):
        result[str(region)] = {
            "co2_tons": float(group["CO2_Reduction_Tons_per_Year"].sum()),
            "installations": int(group["Solar_Installations_Count"].sum()),
            "production_kwh": int(group["Avg_Annual_Production_kWh"].sum()),
        }
    return result


def country_totals_unrounded(df: pd.DataFrame) -> dict[str, dict[str, float]]:
    """Unrounded per-country group sums, keyed by country name.

    Used for exact reconciliation testing — never round these before
    summing or comparing against the raw CSV totals.
    """
    result: dict[str, dict[str, float]] = {}
    for country, group in df.groupby("Country"):
        result[str(country)] = {
            "co2_tons": float(group["CO2_Reduction_Tons_per_Year"].sum()),
            "installations": int(group["Solar_Installations_Count"].sum()),
            "production_kwh": int(group["Avg_Annual_Production_kWh"].sum()),
        }
    return result
