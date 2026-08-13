# Solar Energy Worldwide — analysis and dashboard

An analysis of `solar_energy_worldwide.csv` (48 cities, 30 countries, 17 columns)
and a self-contained interactive dashboard built from it.

## What it says

- **Where solar is installed has almost nothing to do with where it pays back.**
  Installations and ROI correlate at 0.137. Of the twelve cities with the most
  installations and the twelve with the best returns, only four appear in both
  lists. China, India and Europe hold the capacity; Phoenix, Dubai and Cairo hold
  the returns.
- **Four of the seventeen columns carry one column's information.** Estimated
  savings and CO₂ reduction are exact rescalings of annual production, and payback
  is that ratio rounded. Two more columns are constant across all 48 rows.
- **The supplied reference dashboard omits Dubai**, understating total CO₂ by
  6.30 t, total installations by 850, and Asia's CO₂ by 6.30 t — and dropping the
  second-highest-ROI city from its ranking. `test_dubai_present_in_every_rollup`
  guards that defect in the Python rollups and `tests/js/rollup.test.mjs` guards
  it again in the browser-side ones.

## Build

```bash
python -m analysis.build_data       # CSV  -> output/data.json   (validated)
python -m analysis.build_dashboard  # JSON -> output/dashboard.html
```

Both builds fail loud: a missing file, an unexpected column, a null, a rollup that
does not reconcile, or an external reference in the emitted HTML aborts the build
with the specific problem printed and writes nothing.

Open `output/dashboard.html` directly — it makes no network requests of any kind.

## Test

```bash
python -m pytest tests/ -v          # pipeline, assembler, and the harness hooks
node --test "tests/js/*.test.mjs"   # chart geometry, rollups, filter state
```

`tests/test_dashboard_js.py` runs the JavaScript suite from pytest, so
`python -m pytest` alone covers both languages. It skips, loudly, if node is absent.

## Layout

| Path | What it is |
|---|---|
| `analysis/metrics.py` | Derived measures: risk bands, regional rank, production consistency |
| `analysis/aggregate.py` | Region, country and city rollups |
| `analysis/build_data.py` | Validation, reconciliation, `output/data.json` |
| `analysis/build_dashboard.py` | Asset inlining, the self-containment gate, `output/dashboard.html` |
| `analysis/dashboard_assets/` | The shell, stylesheet and JavaScript modules that get inlined |
| `tests/js/` | Chart geometry tests, plus a DOM shim that mounts the whole page |
| `docs/superpowers/specs/` | The approved design |
| `docs/superpowers/plans/` | The two implementation plans |
| `docs/DECISIONS.md` | Choices made between real alternatives, with reasons |

## How it is put together

`data.json` is the seam. Python validates the CSV, computes every rollup, proves
each one reconciles to the raw totals, and writes the payload. The dashboard build
inlines that payload with the CSS and JavaScript into one HTML file and refuses to
write it unless the result is provably free of external references.

Chart *geometry* is pure JavaScript — functions that take rows and return mark
coordinates, with no DOM involved — so `node --test` asserts the actual numbers.
The browser-side rollups are checked field-for-field against the Python output, so
the two implementations cannot silently drift.

## Definitions

| Measure | Definition |
|---|---|
| Payback risk | Low under 7 years · Medium 7 to 9 inclusive · High above 9 |
| Regional ROI rank | Dense rank on mean `ROI_Percentage`, descending |
| Production consistency | 1 − (σ ÷ μ) of `Avg_Annual_Production_kWh` within region, sample σ, clamped to 0–1; not computable under 3 cities |

## Caveats

`Electricity_Price_USD_per_kWh` (0.15) and `Avg_System_Cost_USD` (15000) are
constant across all rows, so no price or cost comparison is possible. Dubai is
labelled `Region = Asia` with `Country = UAE` in the source; region values are
preserved rather than recoded, so totals reconcile to the raw CSV. The sample is
48 cities — Middle East is one city, Africa and Oceania are three each.
