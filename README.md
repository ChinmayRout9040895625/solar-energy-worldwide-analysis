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

## The data at a glance

<!-- CHARTS:BEGIN -->

**48 cities · 30 countries · 7 regions · 208.35 t CO₂ avoided per year · 2,328,540 installations**

_Generated from `output/data.json` by `analysis/render_readme_charts.py` — do not edit by hand._

```text
Where solar is installed vs where it pays back   r = 0.137

MOST INSTALLATIONS               | BEST RETURN
---------------------------------+------------------------------
  Beijing               609,000 |* Phoenix          17.2%
  Shanghai              609,000 |  Dubai            15.9%
  Chicago               142,000 |  Cairo            15.4%
* Los Angeles           142,000 |* Los Angeles      14.5%
* Miami                 142,000 |  Tel Aviv         14.5%
  New York              142,000 |  Johannesburg     13.9%
* Phoenix               142,000 |  Cape Town        13.5%
  Bangalore              73,000 |* Miami            13.5%
* Delhi                  73,000 |  Athens           13.0%
  Mumbai                 73,000 |  Brisbane         13.0%
  Berlin                 18,500 |* Delhi            13.0%
  Munich                 18,500 |  Madrid           13.0%

* in both lists - 4 of 12
```

```text
Top 12 cities by return on investment

  1. Phoenix       United States   ██████████████████████████████  17.2%
  2. Dubai         UAE             ████████████████████████████··  15.9%
  3. Cairo         Egypt           ███████████████████████████···  15.4%
  4. Los Angeles   United States   █████████████████████████·····  14.5%
  5. Tel Aviv      Israel          █████████████████████████·····  14.5%
  6. Johannesburg  South Africa    ████████████████████████······  13.9%
  7. Cape Town     South Africa    ████████████████████████······  13.5%
  8. Miami         United States   ████████████████████████······  13.5%
  9. Athens        Greece          ███████████████████████·······  13.0%
 10. Brisbane      Australia       ███████████████████████·······  13.0%
 11. Delhi         India           ███████████████████████·······  13.0%
 12. Madrid        Spain           ███████████████████████·······  13.0%
```

```text
Mean ROI against installed base, by region

region         mean ROI                  installations             
Middle East    ████████████████ 14.50%   ················       920
Africa         ████████████████ 14.27%   ················     3,850
Oceania        █████████████··· 12.17%   ················    26,700
North America  █████████████··· 12.03%   ████████········   718,200
Asia           █████████████··· 11.42%   ████████████████ 1,469,100
South America  ████████████···· 10.54%   ················    12,170
Europe         ██████████······  8.85%   █···············    97,600

Europe has the most cities and the lowest return; Asia holds 63% of the
installed base and ranks fifth of seven on return.
```

```text
Payback risk (Low < 7 yrs | Medium 7-9 | High > 9)

Low     ██████························   5 cities
Medium  ████████████████████████······  19 cities
High    ██████████████████████████████  24 cities
```

<!-- CHARTS:END -->

## Build

```bash
python -m analysis.build_data            # CSV  -> output/data.json   (validated)
python -m analysis.build_dashboard       # JSON -> output/dashboard.html
python -m analysis.build_powerbi         # JSON -> output/powerbi/*.pbip
python -m analysis.render_readme_charts  # JSON -> the chart block above
```

## Power BI

`python -m analysis.build_powerbi` writes a Power BI Desktop project; open
`output/powerbi/SolarEnergyWorldwide.pbip`.

**Enable the PBIR preview feature first**, or the report will not load:
File > Options and settings > Options > Preview features >
*Store reports using enhanced metadata format (PBIR)*.

It emits **TMSL** (`model.bim`) for the model and **PBIR** (the `definition/`
folder) for the report. An earlier attempt used PBIR-Legacy (`report.json`) and
opened to a blank canvas: Microsoft documents that file as one that "doesn't
support external editing", so Desktop discards a layout it did not write itself.
PBIR is the format built for external authoring — every file carries a public
JSON schema and Desktop names the offending file if one is malformed.

The 48 rows are embedded in the model as a literal M `#table` rather than read
from the CSV. A file path inside a Power BI query is absolute, so a project
pointing at this machine's CSV would break the moment it moved — the same
self-containment rule the HTML dashboard follows.

The DAX mirrors `analysis/metrics.py`: payback bands at the same 7 / 9 boundaries,
dense regional ROI rank, and production consistency that returns BLANK under three
cities instead of a misleading 1.00. Nothing executes DAX at build time, so those
expressions are translations rather than verified computations — the build prints
the figures to check against:

| Where | Should read |
|---|---|
| Cities / CO₂ / installations cards | 48 · 208.35 t · 2,328,540 |
| Payback risk | Low 5 · Medium 19 · High 24 |
| Regional ROI Rank = 1 | Middle East |
| Asia CO₂ | 54.72 — includes Dubai |

Every build fails loud: a missing file, an unexpected column, a null, a rollup
that does not reconcile, an external reference in the emitted HTML, or a missing
marker pair in this README aborts with the specific problem printed and writes
nothing.

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
| `analysis/build_powerbi.py` | Generates the Power BI Desktop project (PBIP) from the payload |
| `analysis/render_readme_charts.py` | Regenerates this README's chart block from the payload |
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
