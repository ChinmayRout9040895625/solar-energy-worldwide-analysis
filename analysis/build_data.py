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

from analysis.aggregate import city_records, country_records, region_records, totals

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

CAVEATS = (
    "Electricity_Price_USD_per_kWh is constant at 0.15 and "
    "Avg_System_Cost_USD is constant at 15000 across all rows, so no "
    "price or cost comparison is possible.",
    "Estimated savings, payback period, and CO2 reduction are exact "
    "arithmetic functions of annual production, so they carry one "
    "variable's information between them, not three.",
    "Dubai is labelled Region=Asia while Country=UAE, as in the source "
    "data. Region values are preserved, never recoded.",
    "The sample is 48 cities in 30 countries. Regional figures for "
    "Middle East (1 city), Africa (3) and Oceania (3) rest on very few "
    "observations.",
    "Solar_Installations_Count correlates with ROI_Percentage at only "
    "0.137: where solar is deployed is close to unrelated to where it "
    "pays back best.",
)


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


def reconcile(df: pd.DataFrame, payload: dict) -> None:
    """Verify every rollup sums back to the raw CSV. Raise on any mismatch."""
    if len(payload["cities"]) != len(df):
        raise DataValidationError(
            f"cities rollup has {len(payload['cities'])} records "
            f"but the source has {len(df)} rows"
        )

    checks = (
        ("co2_tons", "CO2_Reduction_Tons_per_Year", 0.02),
        ("installations", "Solar_Installations_Count", 0.5),
    )
    for level in ("regions", "countries"):
        for key, column, tolerance in checks:
            rolled = sum(record[key] for record in payload[level])
            raw = df[column].sum()
            if not math.isclose(rolled, raw, abs_tol=tolerance):
                raise DataValidationError(
                    f"{level} rollup of {key} is {rolled} "
                    f"but the source total is {raw}"
                )

    # region_records exposes a summed production_kwh; country_records
    # exposes mean_production_kwh (a per-country mean), so it is
    # reconciled as mean * cities instead of a direct sum.
    regions_production = sum(record["production_kwh"] for record in payload["regions"])
    raw_production = df["Avg_Annual_Production_kWh"].sum()
    if not math.isclose(regions_production, raw_production, abs_tol=0.5):
        raise DataValidationError(
            f"regions rollup of production_kwh is {regions_production} "
            f"but the source total is {raw_production}"
        )

    countries_production = sum(
        record["mean_production_kwh"] * record["cities"] for record in payload["countries"]
    )
    if not math.isclose(countries_production, raw_production, abs_tol=0.5):
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


def build_payload(df: pd.DataFrame) -> dict:
    """Assemble the full data.json structure."""
    return {
        "meta": {
            "source": "solar_energy_worldwide.csv",
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "spec": SPEC,
        },
        "totals": totals(df),
        "caveats": list(CAVEATS),
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
