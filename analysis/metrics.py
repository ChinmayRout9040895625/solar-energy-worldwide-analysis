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
