# Solar Data Pipeline Implementation Plan (Plan A of 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the analysis pipeline that turns `solar_energy_worldwide.csv` into a validated `output/data.json`, with every aggregate proven to reconcile against the raw CSV.

**Architecture:** Three focused modules. `metrics.py` holds pure derived-measure functions with no I/O. `aggregate.py` builds region, country, and city rollups. `build_data.py` validates the input, orchestrates the other two, and writes `output/data.json`. Data flows one direction only; nothing reaches backwards.

**Tech Stack:** Python 3.14, pandas 3.0.5, pytest. Unlike the hook code in `.claude/hooks/`, pandas IS permitted here — this is the analysis path, not the hook path.

**Scope:** Plan A ends at `output/data.json`. All dashboard rendering — `build_dashboard.py`, `analysis/charts/`, HTML, SVG, `tests/test_build.py` — is Plan B and out of scope here.

## Global Constraints

- **Never modify `solar_energy_worldwide.csv`.** It is the source of truth, read-only.
- **Never recode `Region`.** Dubai stays `Region = Asia` with `Country = UAE`; the caveat is documented in the output, not corrected in the data.
- **The build fails loud and stops.** A missing file, unexpected or missing column, any null, or a rollup that does not reconcile to the raw total aborts with the specific mismatch printed. This is deliberately the opposite of `.claude/hooks/`, which fails open.
- **Payback risk bands:** Low `< 7.0`; Medium `>= 7.0 and <= 9.0`; High `> 9.0`.
- **Production consistency:** `1 - (σ / μ)` of `Avg_Annual_Production_kWh` within region, sample standard deviation (`ddof=1`), clamped to `[0.0, 1.0]`. `None` for regions with fewer than 3 cities. Small-sample marker for fewer than 5.
- **Regional ROI rank:** dense rank on mean `ROI_Percentage`, descending, 1-based.
- **Money and score rounding:** round floats to 2 decimals in emitted JSON. Never round intermediate values used in further arithmetic.
- Git identity is not configured globally. Commit with `git -c user.name="chinm" -c user.email="mishraswagat2804@gmail.com" commit -m "..."`.
- Run tests with `python -m pytest`. Windows; use forward slashes in paths.

## Verified dataset facts (assert these, do not recompute expectations)

| Quantity | Exact value |
|---|---|
| Cities | 48 |
| Countries | 30 |
| Regions | 7 |
| Total CO₂ reduction | 208.35 |
| Total installations | 2,328,540 |
| Total annual production | 520,875 |
| Payback band counts | Low 5, Medium 19, High 24 |
| Rows with payback exactly 7.0 or 9.0 | **0 and 0** — boundaries are untestable from real data; use synthetic frames |
| CO₂ by region | Africa 17.10, Asia 54.72, Europe 56.70, Middle East 5.76, North America 38.43, Oceania 14.58, South America 21.06 |
| Regional ROI rank | 1 Middle East 14.50, 2 Africa 14.2667, 3 Oceania 12.1667, 4 North America 12.025, 5 Asia 11.425, 6 South America 10.54, 7 Europe 8.85 |
| Production consistency | Africa 0.9343, Asia 0.8264, Europe 0.7454, Middle East None, North America 0.7616, Oceania 0.9020, South America 0.8412 |
| Cities per region | Europe 16, Asia 12, North America 8, South America 5, Oceania 3, Africa 3, Middle East 1 |
| Dubai | Region Asia, Country UAE, ROI 15.9, CO₂ 6.3, installations 850, production 15750, payback 6.3 |
| Top 3 by ROI | Phoenix 17.2, **Dubai 15.9**, Cairo 15.4 |

## File Structure

| File | Responsibility |
|---|---|
| `analysis/__init__.py` | Package marker (empty) |
| `analysis/metrics.py` | Pure derived-measure functions. No file I/O, no printing. |
| `analysis/aggregate.py` | Region / country / city rollups as plain dicts |
| `analysis/build_data.py` | Input validation, orchestration, JSON emission, CLI entry |
| `tests/test_metrics.py` | Every formula, including synthetic boundary cases |
| `tests/test_aggregate.py` | Reconciliation against raw CSV + the Dubai regression test |
| `tests/test_build_data.py` | Validation failures and emitted-JSON shape |

---

### Task 1: Payback risk bands

**Files:**
- Create: `analysis/__init__.py` (empty)
- Create: `analysis/metrics.py`
- Test: `tests/test_metrics.py`

**Interfaces:**
- Consumes: nothing
- Produces: `PAYBACK_LOW_MAX: float = 7.0`, `PAYBACK_MEDIUM_MAX: float = 9.0`, `payback_risk_band(years: float) -> str` returning exactly `"Low"`, `"Medium"`, or `"High"`, and `payback_band_counts(df: pd.DataFrame) -> dict[str, int]` returning all three keys always, zero-filled when a band is empty.

- [ ] **Step 1: Create the package marker**

Create `analysis/__init__.py` as an empty file.

- [ ] **Step 2: Write the failing test**

Create `tests/test_metrics.py`:

```python
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_metrics.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'analysis.metrics'`

- [ ] **Step 4: Write the implementation**

Create `analysis/metrics.py`:

```python
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_metrics.py -v`
Expected: 7 passed

- [ ] **Step 6: Commit**

```bash
git add analysis/__init__.py analysis/metrics.py tests/test_metrics.py
git commit -m "feat: add payback risk band classification"
```

---

### Task 2: Regional ROI rank

**Files:**
- Modify: `analysis/metrics.py` (append)
- Test: `tests/test_metrics.py` (append)

**Interfaces:**
- Consumes: nothing from Task 1
- Produces: `regional_roi_rank(df: pd.DataFrame) -> dict[str, int]` mapping region name to 1-based dense rank on mean `ROI_Percentage` descending, and `regional_mean_roi(df: pd.DataFrame) -> dict[str, float]` returning unrounded means.

Dense rank means tied regions share a rank and the next rank is not skipped. Region names are the raw `Region` values, never recoded.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_metrics.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_metrics.py -v`
Expected: FAIL with `ImportError: cannot import name 'regional_mean_roi'`

- [ ] **Step 3: Write the implementation**

Append to `analysis/metrics.py`:

```python
def regional_mean_roi(df: pd.DataFrame) -> dict[str, float]:
    """Mean ROI percentage per region, unrounded."""
    return df.groupby("Region")["ROI_Percentage"].mean().to_dict()


def regional_roi_rank(df: pd.DataFrame) -> dict[str, int]:
    """1-based dense rank of regions by mean ROI, highest first."""
    means = df.groupby("Region")["ROI_Percentage"].mean()
    ranks = means.rank(method="dense", ascending=False).astype(int)
    return ranks.to_dict()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_metrics.py -v`
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add analysis/metrics.py tests/test_metrics.py
git commit -m "feat: add regional ROI dense ranking"
```

---

### Task 3: Production consistency with the n/a rule

**Files:**
- Modify: `analysis/metrics.py` (append)
- Test: `tests/test_metrics.py` (append)

**Interfaces:**
- Consumes: nothing from Tasks 1-2
- Produces: `MIN_CITIES_FOR_CONSISTENCY: int = 3`, `SMALL_SAMPLE_MAX: int = 5`, `production_consistency(df: pd.DataFrame) -> dict[str, float | None]` (`None` means not computable), `small_sample_regions(df: pd.DataFrame) -> set[str]`, and `cities_per_region(df: pd.DataFrame) -> dict[str, int]`.

`None` for a region with fewer than 3 cities is load-bearing: a single-city region has zero variance, which would otherwise render as perfect consistency (1.0) and mislead the reader. Emitting `None` forces the dashboard to print n/a.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_metrics.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_metrics.py -v`
Expected: FAIL with `ImportError: cannot import name 'MIN_CITIES_FOR_CONSISTENCY'`

- [ ] **Step 3: Write the implementation**

Append to `analysis/metrics.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_metrics.py -v`
Expected: 20 passed

- [ ] **Step 5: Commit**

```bash
git add analysis/metrics.py tests/test_metrics.py
git commit -m "feat: add production consistency with insufficient-sample rule"
```

---

### Task 4: Rollups and reconciliation

**Files:**
- Create: `analysis/aggregate.py`
- Test: `tests/test_aggregate.py`

**Interfaces:**
- Consumes: from `analysis.metrics` — `payback_band_counts`, `regional_roi_rank`, `regional_mean_roi`, `production_consistency`, `small_sample_regions`, `cities_per_region`, `payback_risk_band`
- Produces:
  - `city_records(df) -> list[dict]` — one dict per city, sorted by `ROI_Percentage` descending then `City` ascending. Keys: `city`, `country`, `region`, `lat`, `lon`, `ghi`, `sunlight_hours`, `installations`, `production_kwh`, `savings_usd`, `payback_years`, `roi_pct`, `co2_tons`, `viability`, `risk_band`.
  - `region_records(df) -> list[dict]` — one per region, sorted by `rank` ascending. Keys: `region`, `cities`, `rank`, `mean_roi`, `co2_tons`, `installations`, `production_kwh`, `consistency`, `small_sample`, `risk_counts`.
  - `country_records(df) -> list[dict]` — one per country, sorted by `co2_tons` descending then `country` ascending. Keys: `country`, `region`, `cities`, `mean_roi`, `mean_production_kwh`, `co2_tons`, `installations`.
  - `totals(df) -> dict` — keys `cities`, `countries`, `regions`, `co2_tons`, `installations`, `production_kwh`.

`consistency` is `None` where not computable. All emitted floats are rounded to 2 decimals; the unrounded values are used for sorting and ranking first.

- [ ] **Step 1: Write the failing test**

Create `tests/test_aggregate.py`:

```python
import math
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.aggregate import (
    city_records,
    country_records,
    region_records,
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
    rolled = sum(r["co2_tons"] for r in region_records(real))
    assert math.isclose(rolled, real["CO2_Reduction_Tons_per_Year"].sum(), abs_tol=0.02)


def test_region_installations_reconcile_to_raw_total(real):
    rolled = sum(r["installations"] for r in region_records(real))
    assert rolled == int(real["Solar_Installations_Count"].sum())


def test_region_production_reconciles_to_raw_total(real):
    rolled = sum(r["production_kwh"] for r in region_records(real))
    assert rolled == int(real["Avg_Annual_Production_kWh"].sum())


def test_region_city_counts_sum_to_48(real):
    assert sum(r["cities"] for r in region_records(real)) == 48


def test_country_co2_reconciles_to_raw_total(real):
    rolled = sum(r["co2_tons"] for r in country_records(real))
    assert math.isclose(rolled, real["CO2_Reduction_Tons_per_Year"].sum(), abs_tol=0.02)


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_aggregate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'analysis.aggregate'`

- [ ] **Step 3: Write the implementation**

Create `analysis/aggregate.py`:

```python
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
        records.append(
            {
                "country": str(country),
                "region": str(group["Region"].iloc[0]),
                "cities": int(len(group)),
                "mean_roi": _round2(group["ROI_Percentage"].mean()),
                "mean_production_kwh": _round2(
                    group["Avg_Annual_Production_kWh"].mean()
                ),
                "co2_tons": _round2(group["CO2_Reduction_Tons_per_Year"].sum()),
                "installations": int(group["Solar_Installations_Count"].sum()),
            }
        )
    # Sort on the UNROUNDED total: the Global Constraints forbid ranking on
    # a rounded value. The helper key is removed before returning so the
    # emitted key set stays exactly as Task 5 asserts it.
    records.sort(key=lambda r: (-r["_co2_unrounded"], r["country"]))
    for record in records:
        del record["_co2_unrounded"]
    return records
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_aggregate.py -v`
Expected: 19 passed

- [ ] **Step 5: Run the whole suite to confirm nothing regressed**

Run: `python -m pytest tests/ -q`
Expected: all tests pass, including the 61 pre-existing harness tests

- [ ] **Step 6: Commit**

```bash
git add analysis/aggregate.py tests/test_aggregate.py
git commit -m "feat: add region/country/city rollups with reconciliation tests"
```

---

### Task 5: Validation, orchestration, and data.json

**Files:**
- Create: `analysis/build_data.py`
- Create: `output/.gitkeep` (if not already present)
- Modify: `.gitignore` (add `output/data.json`)
- Test: `tests/test_build_data.py`

**Interfaces:**
- Consumes: from `analysis.aggregate` — `city_records`, `region_records`, `country_records`, `totals`
- Produces:
  - `REQUIRED_COLUMNS: tuple[str, ...]` — the 17 expected column names
  - `class DataValidationError(Exception)`
  - `validate(df: pd.DataFrame) -> None` — raises `DataValidationError` with a specific message
  - `reconcile(df: pd.DataFrame, payload: dict) -> None` — raises `DataValidationError` on any mismatch
  - `build_payload(df: pd.DataFrame) -> dict` — the full `data.json` structure
  - `build(csv_path: Path, out_path: Path) -> dict` — validate, build, reconcile, write, return payload
  - `main(argv: list[str] | None = None) -> int` — CLI entry, returns 0 on success and 1 on `DataValidationError`

The emitted payload shape:

```python
{
  "meta": {"source": str, "generated_utc": str, "spec": str},
  "totals": {...},          # from totals()
  "caveats": [str, ...],    # data limitations, rendered by the dashboard
  "cities": [...],
  "regions": [...],
  "countries": [...],
}
```

Caveats live in the data rather than the HTML so the dashboard renders them from one source.

- [ ] **Step 1: Write the failing test**

Create `tests/test_build_data.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_build_data.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'analysis.build_data'`

- [ ] **Step 3: Write the implementation**

Create `analysis/build_data.py`:

```python
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
        ("production_kwh", "Avg_Annual_Production_kWh", 0.5),
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
```

Note the `reconcile` call happens **before** the file is written, so a failed reconciliation never leaves a wrong `data.json` on disk.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_build_data.py -v`
Expected: 16 passed

- [ ] **Step 5: Ignore the generated artifact**

`output/data.json` is generated, so it does not belong in git. Add this line to `.gitignore`:

```
output/data.json
```

Confirm `output/.gitkeep` exists so the directory is tracked; create it as an empty file if not.

- [ ] **Step 6: Run the pipeline for real**

Run: `python -m analysis.build_data`

Expected output naming exactly these figures:
```
wrote output/data.json: 48 cities, 30 countries, 7 regions, 208.35 t CO2, 2328540 installations
```

Then confirm the failure path is real by pointing it at a nonexistent file:

Run: `python -m analysis.build_data missing.csv output/scratch.json`
Expected: `BUILD FAILED: source CSV not found: missing.csv` on stderr, exit code 1, and no `output/scratch.json` created.

- [ ] **Step 7: Run the whole suite**

Run: `python -m pytest tests/ -q`
Expected: all tests pass — the 61 pre-existing harness tests plus the 55 added by this plan

- [ ] **Step 8: Commit**

```bash
git add analysis/build_data.py tests/test_build_data.py .gitignore output/.gitkeep
git commit -m "feat: add validated data.json pipeline with fail-loud checks"
```

---

## Plan B preview (not in scope here)

Plan B consumes `output/data.json` and builds the dashboard: `analysis/charts/` modules, `analysis/build_dashboard.py`, the three pages, cross-filtering, the world map, and `tests/test_build.py` asserting the emitted HTML is self-contained. The `dataviz` skill is loaded before any chart code is written, and `frontend-design` informs the visual direction.

## Self-review notes

Spec coverage for the pipeline half of `docs/superpowers/specs/2026-08-13-solar-dashboard-design.md`:

| Spec requirement | Task |
|---|---|
| Payback risk bands (Low <7, Medium 7–9, High >9) | 1 |
| Regional ROI dense rank | 2 |
| Production consistency, n/a under 3 cities, small-sample under 5 | 3 |
| Region / country / city rollups | 4 |
| Reconciliation to raw CSV totals | 4 (rollup tests), 5 (`reconcile`) |
| `test_dubai_present_in_every_rollup` regression test | 4 |
| Fail loud on missing file, bad column, null, mismatch | 5 |
| `output/data.json` as the validated seam | 5 |
| Caveats carried in the data | 5 |
| Never modify the CSV; never recode Region | Global Constraints; no task writes to the CSV |
| Dashboard rendering, charts, HTML | Deferred to Plan B by design |

Type consistency checked: `payback_risk_band` returns the same three string literals used by `payback_band_counts`, `city_records["risk_band"]`, and `region_records["risk_counts"]`. `production_consistency` returns `float | None` and every consumer handles `None`. `regional_roi_rank` and `regional_mean_roi` are both keyed by raw region name and are used together in `region_records`.
