"""Validate the source CSV, build the dashboard payload, write data.json.

This module fails LOUD and stops. That is deliberately the opposite of the
hooks in .claude/hooks/, which fail open so a broken hook can never block a
session. The rules differ because the consequences differ: a silent hook
failure costs some injected context, while a silent pipeline failure ships
wrong numbers.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from pandas.api.types import is_numeric_dtype

from analysis.aggregate import (
    city_records,
    country_records,
    country_totals_unrounded,
    region_records,
    region_totals_unrounded,
    totals,
)

REQUIRED_COLUMNS = (
    "City",
    "Country",
    "Latitude",
    "Longitude",
    "Annual_Sunlight_Hours",
    "Daily_Peak_Sun_Hours",
    "GHI_kWh_per_m2",
    "Electricity_Price_USD_per_kWh",
    "Solar_Installations_Count",
    "Avg_System_Cost_USD",
    "Avg_Annual_Production_kWh",
    "Estimated_Annual_Savings_USD",
    "Payback_Period_Years",
    "ROI_Percentage",
    "CO2_Reduction_Tons_per_Year",
    "Solar_Viability_Score",
    "Region",
)

SPEC = "docs/superpowers/specs/2026-08-13-solar-dashboard-design.md"

# Columns that must carry a numeric dtype. Everything in REQUIRED_COLUMNS
# except the three identifier/label columns.
NON_NUMERIC_COLUMNS = ("City", "Country", "Region")
NUMERIC_COLUMNS = tuple(c for c in REQUIRED_COLUMNS if c not in NON_NUMERIC_COLUMNS)

CORRELATION_PAIRS = {
    "installations_vs_roi": ("Solar_Installations_Count", "ROI_Percentage"),
    "roi_vs_viability": ("ROI_Percentage", "Solar_Viability_Score"),
    "ghi_vs_production": ("GHI_kWh_per_m2", "Avg_Annual_Production_kWh"),
}


def correlations(df: pd.DataFrame) -> dict[str, float]:
    """Pearson correlations the dashboard displays, rounded to 3 decimals."""
    return {
        name: round(float(df[left].corr(df[right])), 3)
        for name, (left, right) in CORRELATION_PAIRS.items()
    }


def caveats(df: pd.DataFrame) -> list[str]:
    """Caveat strings, with statistics computed from the data they describe."""
    r_installations_roi = correlations(df)["installations_vs_roi"]
    return [
        "Electricity_Price_USD_per_kWh is constant at 0.15 and "
        "Avg_System_Cost_USD is constant at 15000 across all rows, so no "
        "price or cost comparison is possible.",
        "Estimated savings and CO2 reduction are exact arithmetic "
        "functions of annual production and payback period is that ratio "
        "rounded to one decimal place, so the three carry one variable's "
        "information between them, not three.",
        "Dubai is labelled Region=Asia while Country=UAE, as in the source "
        "data. Region values are preserved, never recoded.",
        "The sample is 48 cities in 30 countries. Regional figures for "
        "Middle East (1 city), Africa (3) and Oceania (3) rest on very few "
        "observations.",
        "Solar_Installations_Count correlates with ROI_Percentage at only "
        f"{r_installations_roi}: where solar is deployed is close to "
        "unrelated to where it pays back best.",
    ]


class DataValidationError(Exception):
    """Raised when the input data or a computed rollup fails a check."""


def validate(df: pd.DataFrame) -> None:
    """Reject anything that would make the output untrustworthy."""
    if df.empty:
        raise DataValidationError("dataset is empty: 0 rows")

    actual = set(df.columns)
    expected = set(REQUIRED_COLUMNS)

    missing = sorted(expected - actual)
    if missing:
        raise DataValidationError(f"missing required column(s): {missing}")

    unexpected = sorted(actual - expected)
    if unexpected:
        raise DataValidationError(f"unexpected column(s): {unexpected}")

    null_counts = df.isna().sum()
    offenders = sorted(col for col, n in null_counts.items() if n > 0)
    if offenders:
        raise DataValidationError(f"null values in column(s): {offenders}")

    non_numeric = sorted(
        col for col in NUMERIC_COLUMNS if not is_numeric_dtype(df[col])
    )
    if non_numeric:
        raise DataValidationError(
            f"non-numeric dtype in numeric column(s): {non_numeric}"
        )

    duplicates = sorted(df["City"][df["City"].duplicated()].unique().tolist())
    if duplicates:
        raise DataValidationError(f"duplicate City value(s): {duplicates}")

    region_spread = df.groupby("Country")["Region"].nunique()
    for country in sorted(region_spread[region_spread > 1].index.tolist()):
        regions = sorted(df.loc[df["Country"] == country, "Region"].unique().tolist())
        raise DataValidationError(
            f"Country {country!r} spans multiple Region values: {regions}"
        )


def reconcile(df: pd.DataFrame, payload: dict) -> None:
    """Verify every rollup sums back to the raw CSV. Raise on any mismatch."""
    if len(payload["cities"]) != len(df):
        raise DataValidationError(
            f"cities rollup has {len(payload['cities'])} records "
            f"but the source has {len(df)} rows"
        )

    raw_co2 = float(df["CO2_Reduction_Tons_per_Year"].sum())
    raw_installations = int(df["Solar_Installations_Count"].sum())
    raw_production = int(df["Avg_Annual_Production_kWh"].sum())

    # --- cities: catches drops, duplicates, and value corruption together ---
    cities = payload["cities"]
    for key, raw in (
        ("installations", raw_installations),
        ("production_kwh", raw_production),
    ):
        rolled = sum(record[key] for record in cities)
        if rolled != raw:
            raise DataValidationError(
                f"cities rollup of {key} is {rolled} "
                f"but the source total is {raw}"
            )

    # City co2_tons values are each display-rounded to 2 decimals, so the
    # summed error is bounded by 0.005 per city.
    cities_co2 = sum(record["co2_tons"] for record in cities)
    cities_co2_bound = len(cities) * 0.005 + 1e-9
    if not math.isclose(cities_co2, raw_co2, abs_tol=cities_co2_bound):
        raise DataValidationError(
            f"cities rollup of co2_tons is {cities_co2} "
            f"but the source total is {raw_co2}"
        )

    # --- totals: the KPI tile row, asserted field by field ---
    t = payload["totals"]
    for key, raw in (
        ("cities", len(df)),
        ("countries", int(df["Country"].nunique())),
        ("regions", int(df["Region"].nunique())),
        ("installations", raw_installations),
        ("production_kwh", raw_production),
    ):
        if t[key] != raw:
            raise DataValidationError(
                f"totals field {key} is {t[key]} but the source value is {raw}"
            )
    # totals co2_tons is rounded once from the raw sum, not accumulated.
    if not math.isclose(t["co2_tons"], raw_co2, abs_tol=1e-9 + 0.005):
        raise DataValidationError(
            f"totals field co2_tons is {t['co2_tons']} "
            f"but the source total is {raw_co2}"
        )

    # --- regions / countries: exact against unrounded group sums ---
    unrounded = {
        "regions": region_totals_unrounded(df),
        "countries": country_totals_unrounded(df),
    }
    name_key = {"regions": "region", "countries": "country"}
    for level in ("regions", "countries"):
        # The unrounded group sums must themselves reconcile exactly to the
        # raw CSV, and each emitted record must be the display rounding of
        # its own group sum — an exact check, not a tuned tolerance.
        rolled_co2 = sum(v["co2_tons"] for v in unrounded[level].values())
        if not math.isclose(rolled_co2, raw_co2, abs_tol=1e-9):
            raise DataValidationError(
                f"{level} rollup of co2_tons is {rolled_co2} "
                f"but the source total is {raw_co2}"
            )
        for record in payload[level]:
            name = record[name_key[level]]
            expected = round(unrounded[level][name]["co2_tons"], 2)
            if not math.isclose(record["co2_tons"], expected, abs_tol=1e-9):
                raise DataValidationError(
                    f"{level} record {name!r} reports co2_tons "
                    f"{record['co2_tons']} but the source group sum is "
                    f"{expected}"
                )
            if record["installations"] != unrounded[level][name]["installations"]:
                raise DataValidationError(
                    f"{level} record {name!r} reports installations "
                    f"{record['installations']} but the source group sum is "
                    f"{unrounded[level][name]['installations']}"
                )
        rolled_installations = sum(
            record["installations"] for record in payload[level]
        )
        if rolled_installations != raw_installations:
            raise DataValidationError(
                f"{level} rollup of installations is {rolled_installations} "
                f"but the source total is {raw_installations}"
            )

    regions_production = sum(record["production_kwh"] for record in payload["regions"])
    if regions_production != raw_production:
        raise DataValidationError(
            f"regions rollup of production_kwh is {regions_production} "
            f"but the source total is {raw_production}"
        )

    # country_records emits mean_production_kwh (rounded), so the exact
    # check uses country_totals_unrounded instead.
    countries_production = sum(
        v["production_kwh"] for v in unrounded["countries"].values()
    )
    if not math.isclose(countries_production, raw_production, abs_tol=1e-9):
        raise DataValidationError(
            f"countries rollup of production_kwh is {countries_production} "
            f"but the source total is {raw_production}"
        )

    rolled_cities = sum(record["cities"] for record in payload["regions"])
    if rolled_cities != len(df):
        raise DataValidationError(
            f"regions rollup counts {rolled_cities} cities "
            f"but the source has {len(df)} rows"
        )

    rolled_risk = sum(
        sum(record["risk_counts"].values()) for record in payload["regions"]
    )
    if rolled_risk != len(df):
        raise DataValidationError(
            f"regions rollup of risk_counts covers {rolled_risk} cities "
            f"but the source has {len(df)} rows"
        )

    rolled_country_cities = sum(record["cities"] for record in payload["countries"])
    if rolled_country_cities != len(df):
        raise DataValidationError(
            f"countries rollup counts {rolled_country_cities} cities "
            f"but the source has {len(df)} rows"
        )


def build_payload(df: pd.DataFrame) -> dict:
    """Assemble the full data.json structure."""
    return {
        "meta": {
            "source": "solar_energy_worldwide.csv",
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "spec": SPEC,
        },
        "totals": totals(df),
        "correlations": correlations(df),
        "caveats": caveats(df),
        "cities": city_records(df),
        "regions": region_records(df),
        "countries": country_records(df),
    }


def build(csv_path: Path, out_path: Path) -> dict:
    """Validate, build, reconcile, write. Raises DataValidationError."""
    csv_path = Path(csv_path)
    if not csv_path.is_file():
        raise DataValidationError(f"source CSV not found: {csv_path}")

    try:
        df = pd.read_csv(csv_path)
    except Exception as exc:  # malformed CSV, encoding problems
        raise DataValidationError(f"could not read {csv_path}: {exc}") from exc

    validate(df)
    payload = build_payload(df)
    reconcile(df, payload)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build output/data.json")
    parser.add_argument("csv", nargs="?", default="solar_energy_worldwide.csv")
    parser.add_argument("out", nargs="?", default="output/data.json")
    args = parser.parse_args(argv)

    try:
        payload = build(Path(args.csv), Path(args.out))
    except DataValidationError as exc:
        print(f"BUILD FAILED: {exc}", file=sys.stderr)
        return 1

    t = payload["totals"]
    print(
        f"wrote {args.out}: {t['cities']} cities, {t['countries']} countries, "
        f"{t['regions']} regions, {t['co2_tons']} t CO2, "
        f"{t['installations']} installations"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
