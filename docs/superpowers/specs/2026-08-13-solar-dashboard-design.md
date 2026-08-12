# Solar Energy Worldwide — Analysis & Dashboard Design

**Date:** 2026-08-13
**Project:** solar_energy_worldwide_analysis
**Status:** Approved design, ready for implementation planning
**Reference:** supplied Power BI dashboard PDF (5 pages)

## Purpose

Build an analysis of `solar_energy_worldwide.csv` (48 cities, 17 columns) and a self-contained interactive HTML dashboard. The dashboard answers where solar deployment is financially justified, and is finished to portfolio standard.

The supplied Power BI PDF is the reference for structure and analytical intent. Its three themes are kept; its defects are not reproduced.

## Findings that shape this design

All verified against the CSV before designing.

### The reference dashboard silently omits Dubai

| Quantity | Reference | Actual | Difference |
|---|---|---|---|
| Total CO₂ reduction | 202.05 | 208.35 | 6.30 = Dubai |
| Total installations | 2,327,690 | 2,328,540 | 850 = Dubai |
| Asia CO₂ reduction | 48.42 | 54.72 | 6.30 = Dubai |

Dubai has the second-highest ROI in the dataset (15.9%, behind Phoenix at 17.2%) yet is absent from the reference's ROI-by-city ranking. Every regional total on the reference's financial page is understated by Dubai's contribution.

### Two columns are constant

`Electricity_Price_USD_per_kWh` = 0.15 for all 48 rows. `Avg_System_Cost_USD` = 15000 for all 48 rows.

The reference's "Avg Price by Region" therefore plots a constant, and its axis labels read `0.14999999999999997` — floating-point error in an average of identical values, displayed to 17 significant digits. "Investment Efficiency by Region" is derived from these constants.

### Four columns carry one column's worth of information

Verified exactly:
- `Estimated_Annual_Savings_USD` = `Avg_Annual_Production_kWh` × 0.15
- `Payback_Period_Years` = 15000 ÷ `Estimated_Annual_Savings_USD`
- `CO2_Reduction_Tons_per_Year` = `Avg_Annual_Production_kWh` × a single constant ratio

Savings, payback, and CO₂ are deterministic rescalings of production. The reference's "CO2 Reduction vs Annual Production" scatter is a straight line because it plots a variable against itself.

`ROI_Percentage` correlates with `Solar_Viability_Score` at r = 0.982, and `GHI_kWh_per_m2` with production at r = 0.979.

### The strongest genuine finding

Correlation between `Solar_Installations_Count` and `ROI_Percentage` is **0.137** — essentially zero. Where solar is actually deployed has almost nothing to do with where it pays back best. China, India, and Europe dominate installed capacity; Phoenix, Dubai, and Cairo dominate returns. The reference surfaces this nowhere.

### Data classification

Dubai is labelled `Region = Asia` while `Country = UAE`, so the dataset's "Middle East" contains only Tel Aviv.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Reference fidelity | Keep the three themes; fix the defects | Preserves the reference's analytical intent without reproducing its errors |
| Medium | Single self-contained HTML file | Publishable as a shareable artifact; a strict CSP blocks external hosts, so everything is inlined |
| Charting | Hand-built inline SVG, no library | Full visual control; ~200KB total versus ~3.5MB for an inlined Plotly |
| UAE region | Preserve the source value, document the caveat | Totals must reconcile to the raw CSV; recoding invents an editorial judgment the data did not make |
| Derived measures | Define my own, stated explicitly | The reference's formulas live in Power BI and are unrecoverable; matching a number without knowing its definition is worse than defining one |
| Audience | Decision tool, built to portfolio standard | The two goals align here |
| Build failure | Fail loud and stop | Opposite of the harness hooks, deliberately — see Failure behavior |

## Architecture

```
solar_energy_worldwide.csv          source of truth, never modified
analysis/
  metrics.py                        derived measures: risk bands, regional rank, consistency
  aggregate.py                      region / country / city rollups
  build_data.py                     orchestrates → output/data.json
  build_dashboard.py                data.json + templates → output/dashboard.html
  charts/                           one module per chart family (bars, scatter, donut, map)
output/
  data.json                         validated intermediate, ~40KB
  dashboard.html                    the deliverable, self-contained
tests/
  test_metrics.py                   every derived formula, including boundaries
  test_aggregate.py                 rollups reconcile to raw CSV totals
  test_build.py                     emitted HTML is valid and self-contained
```

Data flows one direction: CSV → pandas → derived metrics → aggregates → `data.json` → HTML. No step reaches backwards.

`data.json` exists as a seam so the numbers can be asserted independently of any rendering, and so a chart bug can never be mistaken for a math bug.

## Pages

### Page 1 — Financial performance & investment decisions

- ROI by city: horizontal bars, all 48 cities, sorted descending. Dubai appears at rank 2.
- Payback risk by region: stacked horizontal bars (Low / Medium / High).
- Regional ROI ranking: ordered dot plot, replacing the reference's step chart.
- Installations versus ROI: scatter carrying the r = 0.137 finding, with a written callout.

Cut from the reference: "Avg Price by Region" (constant column), "Investment Efficiency by Region" (constant inputs).

### Page 2 — Production & operational performance

- GHI versus annual production: scatter, colored by region. The real driver relationship.
- Average production by country: horizontal bars.
- Total installations by region: horizontal bars. The reference used an area chart across categories, which implies continuity between Africa and Asia that does not exist.
- Production consistency by region: dot plot, with explicit n/a for single-city regions.

### Page 3 — Sustainability & environmental impact

- CO₂ reduction by country: horizontal bars.
- ROI versus viability score: scatter. Kept, because r = 0.982 is itself the finding.
- Region → country → city matrix: expandable, with correct decimal formatting. The reference renders 26.64 as `26 64`.
- World map: equirectangular projection of lat/long, bubbles sized by installations.
- Data caveats panel: the constant columns, the derived-column collapse, the UAE classification, and n = 48.

Cut from the reference: "CO2 Reduction vs Annual Production" (plots production against itself).

## Derived measures

Each is stated on the dashboard where it appears.

| Measure | Definition | Edge-case rule |
|---|---|---|
| Payback risk | Low < 7 years; Medium 7 to 9 inclusive; High > 9 | Yields 5 / 19 / 24 cities against the actual distribution (min 5.8, median 9.1, max 15.3) |
| Regional ROI rank | Dense rank on mean `ROI_Percentage`, descending | Middle East displayed with an n=1 marker |
| Production consistency | 1 − (σ ÷ μ) of `Avg_Annual_Production_kWh` within region, clamped to [0, 1], sample standard deviation | **n/a** for regions with fewer than 3 cities; small-sample marker for fewer than 5 |

Dropped: `Investment Efficiency` (constant inputs) and the reference's `Savings Reliability Score` (no recoverable definition). Production consistency replaces the latter with a stated formula.

## Interaction

- Region chips and payback-risk chips cross-filter every chart on the page.
- Hover reveals full city detail.
- Clicking a region bar filters to that region.
- One reset control returns to the unfiltered view.
- All filters are keyboard-reachable. No information is hover-only — values stay visible in bars and labels.

Seven regions sits at the limit of a categorical palette, so region color requires a colorblind-safe set. The `dataviz` skill is loaded before any chart code is written; `frontend-design` informs the page's visual direction.

The page is theme-aware: a complete light palette on bare `:root`, with dark overrides under both `prefers-color-scheme` and an explicit `data-theme` attribute.

## Failure behavior

**The build fails loud and stops.** Any of the following aborts with the specific mismatch printed:

- `solar_energy_worldwide.csv` missing or unreadable
- an unexpected or missing column
- any null value
- a regional or country rollup that does not reconcile to the raw CSV total

This is deliberately the opposite of the context-management hooks in the same repository, which fail open so that a broken hook can never block a session. The rules differ because the consequences differ: a silent hook failure costs some injected context, while a silent pipeline failure ships wrong numbers. A dashboard that renders incorrect figures is worse than one that does not render.

## Testing

**Formula tests** (`test_metrics.py`): payback band boundaries at exactly 7.0 and exactly 9.0, the consistency n/a rule for fewer than 3 cities, the small-sample marker at fewer than 5, and rank ties.

**Reconciliation tests** (`test_aggregate.py`): every regional and country rollup sums to the raw CSV total for CO₂, installations, and production. City count sums to 48.

**Build tests** (`test_build.py`): emitted HTML contains no external URL of any scheme, embeds its data inline, and carries all 48 cities in its payload.

**Named regression test**: `test_dubai_present_in_every_rollup`, guarding the exact defect the reference shipped.

## Out of scope

- Modifying `solar_energy_worldwide.csv`
- Reclassifying any region value
- Reproducing Power BI as a file format
- Time-series analysis — the dataset has no temporal dimension
- Any change to the context-management harness
