"""Derived measures for the solar dataset.

Pure functions only: no file I/O, no printing. Every formula here is stated
in docs/superpowers/specs/2026-08-13-solar-dashboard-design.md and surfaced
on the dashboard itself.
"""

from __future__ import annotations

import pandas as pd

PAYBACK_LOW_MAX = 7.0
PAYBACK_MEDIUM_MAX = 9.0

BAND_LOW = "Low"
BAND_MEDIUM = "Medium"
BAND_HIGH = "High"
BANDS = (BAND_LOW, BAND_MEDIUM, BAND_HIGH)


def payback_risk_band(years: float) -> str:
    """Classify a payback period. Low < 7.0 <= Medium <= 9.0 < High."""
    if years < PAYBACK_LOW_MAX:
        return BAND_LOW
    if years <= PAYBACK_MEDIUM_MAX:
        return BAND_MEDIUM
    return BAND_HIGH


def payback_band_counts(df: pd.DataFrame) -> dict[str, int]:
    """Count rows per band. Always returns all three keys, zero-filled."""
    bands = df["Payback_Period_Years"].map(payback_risk_band)
    counts = bands.value_counts().to_dict()
    return {band: int(counts.get(band, 0)) for band in BANDS}


def regional_mean_roi(df: pd.DataFrame) -> dict[str, float]:
    """Mean ROI percentage per region, unrounded."""
    return df.groupby("Region")["ROI_Percentage"].mean().to_dict()


def regional_roi_rank(df: pd.DataFrame) -> dict[str, int]:
    """1-based dense rank of regions by mean ROI, highest first."""
    means = df.groupby("Region")["ROI_Percentage"].mean()
    ranks = means.rank(method="dense", ascending=False).astype(int)
    return ranks.to_dict()


MIN_CITIES_FOR_CONSISTENCY = 3
SMALL_SAMPLE_MAX = 5


def cities_per_region(df: pd.DataFrame) -> dict[str, int]:
    """City count per region."""
    return {str(k): int(v) for k, v in df["Region"].value_counts().items()}


def small_sample_regions(df: pd.DataFrame) -> set[str]:
    """Regions with fewer than SMALL_SAMPLE_MAX cities."""
    return {
        region
        for region, count in cities_per_region(df).items()
        if count < SMALL_SAMPLE_MAX
    }


def production_consistency(df: pd.DataFrame) -> dict[str, float | None]:
    """1 - coefficient of variation of annual production, per region.

    Returns None for regions with fewer than MIN_CITIES_FOR_CONSISTENCY
    cities: a single-city region has zero variance, which would otherwise
    render as perfect consistency and mislead the reader.
    """
    result: dict[str, float | None] = {}
    for region, group in df.groupby("Region")["Avg_Annual_Production_kWh"]:
        if len(group) < MIN_CITIES_FOR_CONSISTENCY:
            result[str(region)] = None
            continue
        mean = group.mean()
        if mean == 0:
            result[str(region)] = None
            continue
        cv = group.std(ddof=1) / mean
        result[str(region)] = max(0.0, min(1.0, 1.0 - cv))
    return result
