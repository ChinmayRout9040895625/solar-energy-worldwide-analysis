# Solar Dashboard Implementation Plan (Plan B of 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the validated `output/data.json` into `output/dashboard.html` — one self-contained, cross-filterable, theme-aware page with hand-built inline SVG charts and no external requests of any kind.

**Architecture:** Python assembles, JavaScript renders. `analysis/build_dashboard.py` reads `output/data.json`, inlines the CSS, the JS modules and the data payload into a shell template, then refuses to write the file unless it is provably self-contained. Chart *geometry* lives in pure JS functions that take rows and return mark specs — no DOM, no globals — so `node --test` can assert every coordinate. A thin render layer turns specs into SVG. Cross-filtering re-runs the same pure functions against the filtered rows, which is why chart code is client-side: a filter changes the layout, not just visibility.

**Tech Stack:** Python 3.14 (stdlib only for this plan — pandas is not needed downstream of `data.json`), Node 22 for `node --test` (built-in runner, zero npm dependencies), hand-written SVG, no chart library.

**Spec:** `docs/superpowers/specs/2026-08-13-solar-dashboard-design.md`

**Predecessor:** `docs/superpowers/plans/2026-08-13-solar-pipeline.md` (Plan A, complete — 133 tests passing)

## Global Constraints

- **Never modify `solar_energy_worldwide.csv`.** Read-only source of truth.
- **Never recode `Region`.** Dubai stays `Region = Asia`, `Country = UAE`. The caveat is rendered, not corrected.
- **The build fails loud and stops.** A missing `data.json`, a missing asset file, or any external reference in the emitted HTML aborts with the specific problem printed and writes nothing. Same posture as `analysis/build_data.py`, opposite of `.claude/hooks/`.
- **No external requests, any scheme.** No `<link>`, no `<script src>`, no `@import`, no `url(...)` that is not a `data:` URI, no `http://` or `https://` or protocol-relative `//` URL. The two SVG/XLink XML *namespace* literals are the only allowed exceptions and are allowlisted by exact string — they are identifiers, never fetched.
- **Numbers are formatted `en-US` explicitly.** `Intl.NumberFormat("en-US", …)`, never the ambient locale. The reference dashboard rendered `26.64` as `26 64`; a locale-dependent separator is how that happens.
- **Dataviz rules are binding** (skill `dataviz`, validated palette in its `references/palette.md`):
  - Categorical region palette, fixed slot order, never cycled. Light: `#2a78d6 #eb6834 #1baf7a #eda100 #e87ba4 #008300 #4a3aa7`. Dark: `#3987e5 #d95926 #199e70 #c98500 #d55181 #008300 #9085e9`. **Already validated for this project** — light: all checks pass, worst adjacent CVD ΔE 9.1, worst adjacent normal-vision ΔE 19.6, contrast WARN on aqua/yellow/magenta; dark: all checks pass including contrast. The WARN obligates the relief rule: visible labels plus a table view, both of which this plan ships.
  - **Region colour is assigned by region name in a fixed order, never by rank or by current filter state.** Filtering out a region must not repaint the survivors.
  - Region colour is used only on *adjacent-pairlist* forms (bars, legends, faceted panels). It is never used to colour a scatter cloud or map bubbles: those are all-pairs forms, where the palette validates only three slots. Seven-region scatter is faceted into small multiples instead.
  - Payback risk is severity, so it uses the reserved **status** palette — good `#0ca30c`, warning `#fab219`, critical `#d03b3b` — always with a label beside it, never colour alone.
  - Marks: bars ≤ 24px thick with a 4px rounded data-end and square baseline; 2px surface gap between touching fills; markers ≥ 8px with a 2px surface ring; hairline solid gridlines, never dashed; hit targets ≥ 24px.
  - No dual axes. No value-ramp on nominal categories. No number on every point — label selectively. Text wears text tokens, never a series colour.
  - Every chart has a table-view twin. Tooltips enhance, never gate.
- **One filter row, above everything it scopes.** Filters re-render every chart, stat and table on the page.
- **Theme:** complete light palette on bare `:root`; dark redefined under both `@media (prefers-color-scheme: dark)` guarded with `:root:not([data-theme="light"])` *and* `:root[data-theme="dark"]`.
- Git identity is not configured globally. Commit with `git -c user.name="chinm" -c user.email="mishraswagat2804@gmail.com" commit -m "..."`.
- Run Python tests with `python -m pytest`. Run JS tests with `node --test "tests/js/*.test.mjs"`. Windows; use forward slashes in paths.

## Verified facts to assert (do not recompute expectations)

| Quantity | Exact value |
|---|---|
| `data.json` top-level keys | `meta totals correlations caveats cities regions countries` |
| Cities / countries / regions | 48 / 30 / 7 |
| Totals | CO₂ 208.35 t, installations 2,328,540, production 520,875 kWh |
| Correlations | `installations_vs_roi` 0.137, `roi_vs_viability` 0.982, `ghi_vs_production` 0.979 |
| Caveats | 5 strings |
| ROI range | 6.5 → 17.2 |
| GHI range | 2.8 → 6.5 |
| Production range | 6,525 → 17,100 |
| Installations range | 150 → 609,000 |
| Viability range | 36 → 73 |
| Lat / lon range | −37.81 → 59.91 / −123.12 → 153.03 |
| Top 3 by ROI | Phoenix 17.2, Dubai 15.9, Cairo 15.4 |
| Region order by ROI rank | Middle East, Africa, Oceania, North America, Asia, South America, Europe |
| Payback bands | Low 5, Medium 19, High 24 |
| Largest country by CO₂ | United States 26.64 t, 5 cities, 710,000 installations |

## Visual direction

The subject is an instrument reading, not a brochure: 48 cities measured, three of them worth acting on. The page is built as a **quiet instrument panel where the data is the only thing allowed to carry colour**. Chips, tabs and controls are ink and hairline only — selection is a 16px bold check and a ghost wash, never a coloured pill — so a region's hue always means that region and nothing else. Personality comes from the type scale rather than from decoration: wide-tracked uppercase eyebrows, a heavy tight display figure, and a hairline definition line under every chart title. Those definition lines are structural, not ornamental — the spec requires each derived measure to be stated where it appears, so the page's most repeated typographic device is carrying a real obligation.

No webfont is loaded, because no external request is permitted and a base64 face would cost more than it returns; the system sans is used at every size, per the dataviz typography rule.

**The signature element** is the page-1 hero: *the mismatch*. Two ranked columns — the twelve largest deployments on the left, the twelve best returns on the right — with connectors drawn only for the cities that appear in both. Almost none do. The hero figure `0.137` sits between them. It is the strongest genuine finding in the dataset, and the reference dashboard surfaces it nowhere.

## File Structure

| File | Responsibility |
|---|---|
| `analysis/build_dashboard.py` | Read `data.json`, inline assets, prove self-containment, write `output/dashboard.html`, CLI entry |
| `analysis/dashboard_assets/shell.html` | Page skeleton with `{{CSS}}`, `{{JS}}`, `{{DATA}}` slots |
| `analysis/dashboard_assets/css/dashboard.css` | Tokens, theme, layout, cards, chips, table styles |
| `analysis/dashboard_assets/js/core.js` | Namespace, `en-US` formatters, linear scale, nice ticks, rounded-bar path |
| `analysis/dashboard_assets/js/rollup.js` | Client-side region/country/totals rollups mirroring `analysis/aggregate.py` |
| `analysis/dashboard_assets/js/filters.js` | Pure filter state + reducer |
| `analysis/dashboard_assets/js/charts_bars.js` | `barSpec`, `stackSpec` |
| `analysis/dashboard_assets/js/charts_dots.js` | `dotSpec` |
| `analysis/dashboard_assets/js/charts_scatter.js` | `scatterSpec`, `facetSpecs`, `nearestMark` |
| `analysis/dashboard_assets/js/charts_map.js` | `mapSpec`, graticule |
| `analysis/dashboard_assets/js/charts_mismatch.js` | `mismatchSpec` — the signature hero |
| `analysis/dashboard_assets/js/render.js` | Spec → SVG DOM, tooltip layer, table-view twin |
| `analysis/dashboard_assets/js/app.js` | Chart registry, tabs, chips, theme toggle, wiring |
| `tests/test_build.py` | Assembly, self-containment, payload, structure |
| `tests/js/load.mjs` | Loads asset scripts into the node test context |
| `tests/js/fakedom.mjs` | Minimal `document` shim for render-layer smoke tests |
| `tests/js/*.test.mjs` | Geometry, rollup, filter tests |
| `tests/test_dashboard_js.py` | Runs `node --test "tests/js/*.test.mjs"` from pytest |

Data flows one direction: `data.json` → inlined payload → filter → rollup → spec → SVG. No step reaches backwards.

---

### Task 1: Assembler, shell, and the self-containment gate

**Files:**
- Create: `analysis/dashboard_assets/shell.html`
- Create: `analysis/dashboard_assets/css/dashboard.css`
- Create: `analysis/dashboard_assets/js/boot.js`
- Create: `analysis/build_dashboard.py`
- Modify: `.gitignore` (add `output/dashboard.html`)
- Test: `tests/test_build.py`

**Interfaces:**
- Consumes: `output/data.json` produced by `analysis/build_data.py`
- Produces:
  - `ASSET_ORDER: tuple[str, ...]` — asset paths relative to `analysis/dashboard_assets/`, in load order
  - `ALLOWED_URL_LITERALS: tuple[str, ...]`
  - `class DashboardBuildError(Exception)`
  - `assert_self_contained(html: str) -> None`
  - `embed_json(payload: dict) -> str`
  - `render_html(payload: dict) -> str`
  - `build(data_path: Path, out_path: Path) -> str`
  - `main(argv: list[str] | None = None) -> int`

`ASSET_ORDER` grows as later tasks add modules. Every later task that adds a JS file appends it here and adds an inline-marker assertion to `tests/test_build.py`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_build.py`:

```python
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.build_dashboard import (
    ALLOWED_URL_LITERALS,
    ASSET_ORDER,
    DashboardBuildError,
    assert_self_contained,
    build,
    embed_json,
    render_html,
    main,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "output" / "data.json"
ASSETS = ROOT / "analysis" / "dashboard_assets"


@pytest.fixture(scope="module")
def payload() -> dict:
    if not DATA.is_file():
        pytest.fail("output/data.json missing — run `python -m analysis.build_data`")
    return json.loads(DATA.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def html(payload) -> str:
    return render_html(payload)


def test_every_declared_asset_exists():
    missing = [name for name in ASSET_ORDER if not (ASSETS / name).is_file()]
    assert missing == []


def test_shell_declares_all_three_slots():
    shell = (ASSETS / "shell.html").read_text(encoding="utf-8")
    for slot in ("{{CSS}}", "{{JS}}", "{{DATA}}"):
        assert slot in shell


def test_no_slot_survives_rendering(html):
    for slot in ("{{CSS}}", "{{JS}}", "{{DATA}}"):
        assert slot not in html


def test_html_has_no_external_references(html):
    assert_self_contained(html)  # must not raise


def test_scanner_rejects_a_stylesheet_link():
    with pytest.raises(DashboardBuildError) as excinfo:
        assert_self_contained('<link rel="stylesheet" href="x.css">')
    assert "link" in str(excinfo.value).lower()


def test_scanner_rejects_an_https_url():
    with pytest.raises(DashboardBuildError) as excinfo:
        assert_self_contained("<p>see https://example.com/x.png</p>")
    assert "https://example.com" in str(excinfo.value)


def test_scanner_rejects_a_protocol_relative_url():
    with pytest.raises(DashboardBuildError):
        assert_self_contained('<script src="//cdn.example.com/x.js"></script>')


def test_scanner_rejects_a_css_import():
    with pytest.raises(DashboardBuildError):
        assert_self_contained("<style>@import 'other.css';</style>")


def test_scanner_rejects_a_remote_css_url():
    with pytest.raises(DashboardBuildError):
        assert_self_contained("<style>body{background:url(bg.png)}</style>")


def test_scanner_allows_a_data_uri():
    assert_self_contained("<style>body{background:url(data:image/gif;base64,R0lGOD)}</style>")


def test_scanner_allows_the_svg_namespace_literal():
    # createElementNS needs this exact string; it is an identifier, not a fetch.
    assert_self_contained('<script>const NS="http://www.w3.org/2000/svg";</script>')


def test_allowed_literals_are_namespaces_only():
    assert set(ALLOWED_URL_LITERALS) == {
        "http://www.w3.org/2000/svg",
        "http://www.w3.org/1999/xlink",
    }


def test_payload_is_embedded_and_parseable(html):
    start = html.index('<script type="application/json" id="solar-data">')
    start = html.index(">", start) + 1
    end = html.index("</script>", start)
    embedded = json.loads(html[start:end])
    assert len(embedded["cities"]) == 48
    assert embedded["totals"]["installations"] == 2328540


def test_embedded_json_cannot_close_the_script_tag(payload):
    hostile = dict(payload)
    hostile["caveats"] = ["</script><img onerror=alert(1)>"]
    assert "</script>" not in embed_json(hostile)
    assert "\\u003c" in embed_json(hostile)


def test_every_js_asset_is_inlined(html):
    for name in ASSET_ORDER:
        if name.endswith(".js"):
            source = (ASSETS / name).read_text(encoding="utf-8")
            probe = next(line for line in source.splitlines() if line.strip())
            assert probe.strip() in html


def test_css_is_inlined(html):
    assert "--series-1" in html
    assert "<style>" in html


def test_html_carries_no_link_or_script_src(html):
    assert "<link" not in html.lower()
    assert "src=" not in html.lower()


def test_three_tab_panels_are_present(html):
    for page in ("page-financial", "page-production", "page-sustainability"):
        assert f'id="{page}"' in html


def test_caveats_are_rendered_from_the_data(payload, html):
    assert len(payload["caveats"]) == 5
    for caveat in payload["caveats"]:
        fragment = caveat.split(".")[0][:40]
        assert fragment in html


def test_title_names_the_project(html):
    assert "<title>" in html
    assert "Solar" in html


def test_build_writes_the_file(tmp_path):
    out = tmp_path / "dashboard.html"
    html = build(DATA, out)
    assert out.exists()
    assert out.read_text(encoding="utf-8") == html


def test_build_creates_missing_parent_directory(tmp_path):
    out = tmp_path / "nested" / "deeper" / "dashboard.html"
    build(DATA, out)
    assert out.exists()


def test_build_raises_on_missing_data_json(tmp_path):
    with pytest.raises(DashboardBuildError) as excinfo:
        build(tmp_path / "absent.json", tmp_path / "dashboard.html")
    assert "absent.json" in str(excinfo.value)


def test_build_raises_on_malformed_data_json(tmp_path):
    broken = tmp_path / "data.json"
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(DashboardBuildError):
        build(broken, tmp_path / "dashboard.html")


def test_build_raises_when_a_required_key_is_missing(tmp_path, payload):
    trimmed = {k: v for k, v in payload.items() if k != "cities"}
    path = tmp_path / "data.json"
    path.write_text(json.dumps(trimmed), encoding="utf-8")
    with pytest.raises(DashboardBuildError) as excinfo:
        build(path, tmp_path / "dashboard.html")
    assert "cities" in str(excinfo.value)


def test_failed_build_writes_nothing(tmp_path):
    out = tmp_path / "dashboard.html"
    with pytest.raises(DashboardBuildError):
        build(tmp_path / "absent.json", out)
    assert not out.exists()


def test_main_returns_zero_on_success(tmp_path):
    assert main([str(DATA), str(tmp_path / "dashboard.html")]) == 0


def test_main_returns_one_on_failure(tmp_path):
    assert main([str(tmp_path / "absent.json"), str(tmp_path / "dashboard.html")]) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_build.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'analysis.build_dashboard'`

- [ ] **Step 3: Write the shell template**

Create `analysis/dashboard_assets/shell.html`:

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Where solar pays back — 48 cities</title>
<style>{{CSS}}</style>
</head>
<body>
<div class="viz-root" id="app">

  <header class="masthead">
    <p class="eyebrow">Solar energy worldwide &middot; 48 cities &middot; 30 countries</p>
    <h1>Where solar pays back</h1>
    <p class="standfirst">Deployment and return are two different maps. This page reads
    one dataset of 48 cities three ways &mdash; what it costs back, what it produces, and
    what it saves in carbon &mdash; and states the definition of every measure beside it.</p>
    <button type="button" id="theme-toggle" class="ghost-button" aria-pressed="false">
      Dark theme
    </button>
  </header>

  <section class="kpis" id="kpis" aria-label="Dataset totals"></section>

  <nav class="tabs" id="tabs" role="tablist" aria-label="Dashboard pages">
    <button type="button" role="tab" id="tab-financial" aria-controls="page-financial"
            aria-selected="true" class="tab">Financial performance</button>
    <button type="button" role="tab" id="tab-production" aria-controls="page-production"
            aria-selected="false" class="tab">Production</button>
    <button type="button" role="tab" id="tab-sustainability" aria-controls="page-sustainability"
            aria-selected="false" class="tab">Sustainability</button>
  </nav>

  <form class="filters" id="filters" aria-label="Filters">
    <fieldset class="chipset" id="region-chips">
      <legend class="eyebrow">Region</legend>
    </fieldset>
    <fieldset class="chipset" id="risk-chips">
      <legend class="eyebrow">Payback risk</legend>
    </fieldset>
    <div class="filter-actions">
      <button type="button" id="reset-filters" class="ghost-button">Reset filters</button>
      <label class="switch">
        <input type="checkbox" id="toggle-tables">
        <span>Show values as tables</span>
      </label>
      <p class="filter-readout" id="filter-readout" role="status"></p>
    </div>
  </form>

  <main>
    <section class="page" id="page-financial" role="tabpanel" aria-labelledby="tab-financial"></section>
    <section class="page" id="page-production" role="tabpanel" aria-labelledby="tab-production" hidden></section>
    <section class="page" id="page-sustainability" role="tabpanel" aria-labelledby="tab-sustainability" hidden></section>
  </main>

  <footer class="colophon">
    <h2 class="eyebrow">What this data cannot tell you</h2>
    <ul class="caveats" id="caveats"></ul>
    <p class="meta" id="meta"></p>
  </footer>

</div>

<script type="application/json" id="solar-data">{{DATA}}</script>
<script>{{JS}}</script>
</body>
</html>
```

- [ ] **Step 4: Write the stylesheet**

Create `analysis/dashboard_assets/css/dashboard.css`. Values are the dataviz reference palette; the region slots are the validated seven-slot order.

```css
:root {
  color-scheme: light;
  --plane: #f9f9f7;
  --surface-1: #fcfcfb;
  --text-primary: #0b0b0b;
  --text-secondary: #52514e;
  --text-muted: #898781;
  --grid: #e1e0d9;
  --axis: #c3c2b7;
  --hairline: rgba(11, 11, 11, 0.10);
  --series-1: #2a78d6;
  --series-2: #eb6834;
  --series-3: #1baf7a;
  --series-4: #eda100;
  --series-5: #e87ba4;
  --series-6: #008300;
  --series-7: #4a3aa7;
  --status-good: #0ca30c;
  --status-warning: #fab219;
  --status-critical: #d03b3b;
  --context: #d6d5cd;
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --plane: #0d0d0d;
    --surface-1: #1a1a19;
    --text-primary: #ffffff;
    --text-secondary: #c3c2b7;
    --text-muted: #898781;
    --grid: #2c2c2a;
    --axis: #383835;
    --hairline: rgba(255, 255, 255, 0.10);
    --series-1: #3987e5;
    --series-2: #d95926;
    --series-3: #199e70;
    --series-4: #c98500;
    --series-5: #d55181;
    --series-6: #008300;
    --series-7: #9085e9;
    --context: #3a3a37;
  }
}

:root[data-theme="dark"] {
  color-scheme: dark;
  --plane: #0d0d0d;
  --surface-1: #1a1a19;
  --text-primary: #ffffff;
  --text-secondary: #c3c2b7;
  --text-muted: #898781;
  --grid: #2c2c2a;
  --axis: #383835;
  --hairline: rgba(255, 255, 255, 0.10);
  --series-1: #3987e5;
  --series-2: #d95926;
  --series-3: #199e70;
  --series-4: #c98500;
  --series-5: #d55181;
  --series-6: #008300;
  --series-7: #9085e9;
  --context: #3a3a37;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--plane);
  color: var(--text-primary);
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  font-size: 15px;
  line-height: 1.5;
}

.viz-root {
  max-width: 1180px;
  margin: 0 auto;
  padding: 40px 24px 72px;
}

.eyebrow {
  margin: 0 0 8px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.masthead { position: relative; padding-bottom: 24px; }
.masthead h1 {
  margin: 0 0 12px;
  font-size: clamp(34px, 5vw, 56px);
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1.02;
}
.standfirst {
  max-width: 60ch;
  margin: 0;
  color: var(--text-secondary);
}

.ghost-button {
  font: inherit;
  font-size: 13px;
  color: var(--text-secondary);
  background: transparent;
  border: 1px solid var(--hairline);
  border-radius: 999px;
  padding: 6px 14px;
  cursor: pointer;
}
.ghost-button:hover { background: var(--grid); }
.masthead .ghost-button { position: absolute; top: 0; right: 0; }

.kpis {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 1px;
  margin: 32px 0;
  background: var(--hairline);
  border-block: 1px solid var(--hairline);
}
.kpi { background: var(--plane); padding: 16px 18px; }
.kpi .kpi-value {
  display: block;
  font-size: 30px;
  font-weight: 700;
  letter-spacing: -0.02em;
}
.kpi .kpi-label {
  display: block;
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 2px;
}

.tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--hairline); }
.tab {
  font: inherit;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-muted);
  background: transparent;
  border: 0;
  border-bottom: 2px solid transparent;
  padding: 10px 14px;
  margin-bottom: -1px;
  cursor: pointer;
}
.tab[aria-selected="true"] {
  color: var(--text-primary);
  border-bottom-color: var(--text-primary);
}

.filters {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 24px;
  padding: 20px 0;
  border-bottom: 1px solid var(--hairline);
}
.chipset { border: 0; margin: 0; padding: 0; }
.chipset legend { padding: 0; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-secondary);
  border: 1px solid var(--hairline);
  border-radius: 999px;
  padding: 5px 12px;
  cursor: pointer;
  user-select: none;
}
.chip:hover { background: var(--grid); }
.chip input { position: absolute; opacity: 0; width: 0; height: 0; }
.chip input:focus-visible + .chip-body { outline: 2px solid var(--text-primary); outline-offset: 3px; }
.chip-body { display: inline-flex; align-items: center; gap: 6px; }
.chip-check { width: 16px; font-weight: 700; visibility: hidden; }
.chip[data-selected="true"] { color: var(--text-primary); border-color: var(--text-primary); }
.chip[data-selected="true"] .chip-check { visibility: visible; }
.chip-key { width: 10px; height: 10px; border-radius: 2px; flex: none; }

.filter-actions { display: flex; align-items: center; gap: 16px; margin-left: auto; }
.switch { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; color: var(--text-secondary); }
.filter-readout { margin: 0; font-size: 13px; color: var(--text-muted); }

.page { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; padding-top: 24px; }
.card {
  margin: 0;
  background: var(--surface-1);
  border: 1px solid var(--hairline);
  border-radius: 10px;
  padding: 20px;
  min-width: 0;
}
.card.wide { grid-column: 1 / -1; }
.card h3 { margin: 0 0 4px; font-size: 17px; font-weight: 650; letter-spacing: -0.01em; }
.card .definition {
  margin: 0 0 16px;
  padding-top: 8px;
  border-top: 1px solid var(--hairline);
  font-size: 12px;
  color: var(--text-muted);
  max-width: 62ch;
}
.card figcaption { margin: 0; }
.plot { overflow-x: auto; }
.plot svg { display: block; max-width: 100%; height: auto; }
.callout {
  margin: 12px 0 0;
  font-size: 13px;
  color: var(--text-secondary);
  max-width: 62ch;
}

.legend { display: flex; flex-wrap: wrap; gap: 12px; margin: 0 0 12px; padding: 0; list-style: none; }
.legend li { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text-secondary); }
.legend .swatch { width: 12px; height: 12px; border-radius: 2px; flex: none; }

.values { width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 12px; font-variant-numeric: tabular-nums; }
.values caption { text-align: left; color: var(--text-muted); padding-bottom: 6px; }
.values th, .values td { text-align: right; padding: 4px 8px; border-bottom: 1px solid var(--hairline); }
.values th:first-child, .values td:first-child { text-align: left; }
.values thead th { color: var(--text-muted); font-weight: 600; }

.tooltip {
  position: fixed;
  z-index: 10;
  pointer-events: none;
  background: var(--surface-1);
  border: 1px solid var(--hairline);
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 12px;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.12);
  max-width: 260px;
}
.tooltip[hidden] { display: none; }
.tooltip .tip-value { font-size: 15px; font-weight: 700; }
.tooltip .tip-label { color: var(--text-secondary); }

.colophon { margin-top: 48px; padding-top: 24px; border-top: 1px solid var(--hairline); }
.caveats { margin: 0; padding-left: 18px; max-width: 76ch; color: var(--text-secondary); font-size: 13px; }
.caveats li { margin-bottom: 8px; }
.meta { font-size: 12px; color: var(--text-muted); }

:where(button, input, a):focus-visible { outline: 2px solid var(--text-primary); outline-offset: 2px; }

@media (max-width: 860px) {
  .page { grid-template-columns: minmax(0, 1fr); }
  .filter-actions { margin-left: 0; }
  .masthead .ghost-button { position: static; margin-top: 16px; }
}

@media (prefers-reduced-motion: reduce) {
  * { animation: none !important; transition: none !important; }
}
```

- [ ] **Step 5: Write the boot script**

Create `analysis/dashboard_assets/js/boot.js`. This is the first asset in load order and owns the namespace; later tasks add modules that attach to it.

```js
/* boot.js — namespace and payload access. First asset in ASSET_ORDER. */
globalThis.SOLAR = globalThis.SOLAR || {};

(function (S) {
  "use strict";

  S.readPayload = function (doc) {
    const node = (doc || globalThis.document).getElementById("solar-data");
    if (!node) throw new Error("solar-data payload block missing");
    return JSON.parse(node.textContent);
  };
})(globalThis.SOLAR);
```

- [ ] **Step 6: Write the assembler**

Create `analysis/build_dashboard.py`:

```python
"""Assemble output/dashboard.html from output/data.json and the inline assets.

Fails loud, like analysis/build_data.py and unlike .claude/hooks/. The gate that
matters here is assert_self_contained: a dashboard that silently reaches for a
CDN is broken the moment it is opened offline or pasted behind a strict CSP, and
the failure is invisible until then. Nothing is written unless it passes.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ASSETS = Path(__file__).resolve().parent / "dashboard_assets"

# Load order matters: boot.js owns the namespace, app.js runs last. The
# stylesheet is listed here too so test_every_declared_asset_exists covers it.
ASSET_ORDER = (
    "css/dashboard.css",
    "js/boot.js",
)

REQUIRED_KEYS = ("meta", "totals", "correlations", "caveats", "cities", "regions", "countries")

# XML namespace identifiers. createElementNS requires these exact strings and
# nothing is ever fetched from them.
ALLOWED_URL_LITERALS = (
    "http://www.w3.org/2000/svg",
    "http://www.w3.org/1999/xlink",
)

_EXTERNAL_PATTERNS = (
    (re.compile(r"<link\b", re.I), "<link> element"),
    (re.compile(r"\bsrc\s*=", re.I), "src attribute"),
    (re.compile(r"\bsrcset\s*=", re.I), "srcset attribute"),
    (re.compile(r"@import\b", re.I), "@import rule"),
    (re.compile(r"<iframe\b", re.I), "<iframe> element"),
    (re.compile(r"\bintegrity\s*=", re.I), "integrity attribute (implies a remote asset)"),
    (re.compile(r"https?://\S+", re.I), "absolute URL"),
    (re.compile(r"""(?:href|src)\s*=\s*["']//""", re.I), "protocol-relative URL"),
    (re.compile(r"""url\(\s*(?!["']?(?:data:|#))""", re.I), "non-data url() reference"),
)


class DashboardBuildError(Exception):
    """Raised when the dashboard cannot be assembled or fails a gate."""


def assert_self_contained(html: str) -> None:
    """Reject any reference that would leave the page needing the network."""
    scanned = html
    for literal in ALLOWED_URL_LITERALS:
        scanned = scanned.replace(literal, "")

    for pattern, description in _EXTERNAL_PATTERNS:
        match = pattern.search(scanned)
        if match:
            raise DashboardBuildError(
                f"external reference ({description}): {match.group(0)[:80]!r}"
            )


def embed_json(payload: dict) -> str:
    """Serialise the payload so it cannot break out of its <script> block."""
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _read_assets() -> tuple[str, str]:
    css_parts: list[str] = []
    js_parts: list[str] = []
    for name in ASSET_ORDER:
        path = ASSETS / name
        if not path.is_file():
            raise DashboardBuildError(f"asset not found: {path}")
        text = path.read_text(encoding="utf-8")
        (css_parts if name.endswith(".css") else js_parts).append(text)
    return "\n".join(css_parts), "\n".join(js_parts)


def render_html(payload: dict) -> str:
    """Inline CSS, JS and the payload into the shell. Gate before returning."""
    missing = [key for key in REQUIRED_KEYS if key not in payload]
    if missing:
        raise DashboardBuildError(f"payload missing required key(s): {missing}")

    shell_path = ASSETS / "shell.html"
    if not shell_path.is_file():
        raise DashboardBuildError(f"asset not found: {shell_path}")

    css, js = _read_assets()
    html = shell_path.read_text(encoding="utf-8")
    for slot, value in (("{{CSS}}", css), ("{{JS}}", js), ("{{DATA}}", embed_json(payload))):
        if slot not in html:
            raise DashboardBuildError(f"shell.html is missing the {slot} slot")
        html = html.replace(slot, value)

    assert_self_contained(html)
    return html


def build(data_path: Path, out_path: Path) -> str:
    """Read data.json, render, write. Raises DashboardBuildError."""
    data_path = Path(data_path)
    if not data_path.is_file():
        raise DashboardBuildError(f"data payload not found: {data_path}")

    try:
        payload = json.loads(data_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DashboardBuildError(f"could not parse {data_path}: {exc}") from exc

    html = render_html(payload)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return html


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build output/dashboard.html")
    parser.add_argument("data", nargs="?", default="output/data.json")
    parser.add_argument("out", nargs="?", default="output/dashboard.html")
    args = parser.parse_args(argv)

    try:
        html = build(Path(args.data), Path(args.out))
    except DashboardBuildError as exc:
        print(f"DASHBOARD BUILD FAILED: {exc}", file=sys.stderr)
        return 1

    print(f"wrote {args.out}: {len(html) / 1024:.0f} KB, self-contained")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

`main` writes nothing on failure because `build` raises before `write_text` is reached, and `render_html` runs the gate before returning.

- [ ] **Step 7: Run test to verify it passes**

Run: `python -m pytest tests/test_build.py -v`
Expected: 28 passed

Note: `test_html_carries_no_link_or_script_src` and the scanner both reject `src=` anywhere in the document, including inside JS strings. No asset in this plan uses that substring; if a later task needs it, the fix is to rename the identifier, not to weaken the gate.

- [ ] **Step 8: Build it and open it**

Run: `python -m analysis.build_dashboard`
Expected: `wrote output/dashboard.html: <n> KB, self-contained`

Open `output/dashboard.html` in a browser. Expected: masthead, empty KPI strip, three working-looking tabs (not yet wired), empty filter row, empty pages, empty caveat list. Nothing renders yet — that is correct for this task.

- [ ] **Step 9: Ignore the generated artifact**

Add to `.gitignore` beneath the existing `output/data.json` line:

```
output/dashboard.html
```

- [ ] **Step 10: Commit**

```bash
git add analysis/build_dashboard.py analysis/dashboard_assets tests/test_build.py .gitignore
git -c user.name="chinm" -c user.email="mishraswagat2804@gmail.com" commit -m "feat: add self-contained dashboard assembler and shell"
```

---

### Task 2: JS core — formatters, scales, ticks, and the node test bridge

**Files:**
- Create: `analysis/dashboard_assets/js/core.js`
- Modify: `analysis/build_dashboard.py` (append to `ASSET_ORDER`)
- Create: `tests/js/load.mjs`
- Create: `tests/js/core.test.mjs`
- Create: `tests/test_dashboard_js.py`

**Interfaces:**
- Consumes: `SOLAR` namespace from `boot.js`
- Produces, all on `SOLAR`:
  - `fmtInt(n) -> string` — `en-US` thousands separators, rounded
  - `fmt1(n) -> string`, `fmt2(n) -> string` — fixed decimals, `en-US`
  - `fmtCompact(n) -> string` — `609,000 -> "609K"`, `2328540 -> "2.3M"`
  - `linear(d0, d1, r0, r1) -> (value) => number`
  - `niceStep(raw) -> number`
  - `ticks(min, max, count) -> number[]`
  - `extent(rows, accessor) -> [min, max]`
  - `roundedBarPath(x, y, w, h, r) -> string` — square at `x`, 4px rounded at `x + w`
  - `REGION_SLOTS: string[]` — CSS custom-property names in fixed slot order
  - `regionColorVar(region, allRegions) -> string` — `var(--series-N)`, assigned by sorted region name so the mapping never depends on filter state

- [ ] **Step 1: Write the test loader**

Create `tests/js/load.mjs`:

```js
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import vm from "node:vm";

const here = path.dirname(fileURLToPath(import.meta.url));
export const ROOT = path.resolve(here, "..", "..");
const JS_DIR = path.join(ROOT, "analysis", "dashboard_assets", "js");

/** Run asset scripts in this context and return the SOLAR namespace. */
export function load(...names) {
  for (const name of names) {
    const file = path.join(JS_DIR, name);
    vm.runInThisContext(readFileSync(file, "utf8"), { filename: file });
  }
  return globalThis.SOLAR;
}

/** The payload the dashboard is built from, for cross-language checks. */
export function payload() {
  const file = path.join(ROOT, "output", "data.json");
  return JSON.parse(readFileSync(file, "utf8"));
}
```

- [ ] **Step 2: Write the failing test**

Create `tests/js/core.test.mjs`:

```js
import test from "node:test";
import assert from "node:assert/strict";
import { load } from "./load.mjs";

const S = load("boot.js", "core.js");

test("integers carry en-US thousands separators", () => {
  assert.equal(S.fmtInt(2328540), "2,328,540");
  assert.equal(S.fmtInt(150), "150");
});

test("two-decimal formatting uses a dot, never a locale comma", () => {
  // The reference dashboard rendered 26.64 as "26 64".
  assert.equal(S.fmt2(26.64), "26.64");
  assert.equal(S.fmt2(208.35), "208.35");
  assert.equal(S.fmt2(5), "5.00");
});

test("one-decimal formatting rounds half away from zero", () => {
  assert.equal(S.fmt1(17.25), "17.3");
  assert.equal(S.fmt1(6.5), "6.5");
});

test("compact formatting shortens large counts only", () => {
  assert.equal(S.fmtCompact(609000), "609K");
  assert.equal(S.fmtCompact(2328540), "2.3M");
  assert.equal(S.fmtCompact(850), "850");
  assert.equal(S.fmtCompact(9999), "9,999");
});

test("linear scale maps domain ends onto range ends", () => {
  const x = S.linear(0, 100, 20, 220);
  assert.equal(x(0), 20);
  assert.equal(x(100), 220);
  assert.equal(x(50), 120);
});

test("a degenerate domain collapses to the range start", () => {
  const x = S.linear(5, 5, 0, 300);
  assert.equal(x(5), 0);
});

test("nice steps snap to 1, 2, 5 times a power of ten", () => {
  assert.equal(S.niceStep(1), 1);
  assert.equal(S.niceStep(1.4), 2);
  assert.equal(S.niceStep(3), 5);
  assert.equal(S.niceStep(7), 10);
  assert.equal(S.niceStep(230), 500);
});

test("ticks are clean numbers inside the domain", () => {
  assert.deepEqual(S.ticks(0, 20, 4), [0, 5, 10, 15, 20]);
  assert.deepEqual(S.ticks(0, 17.2, 4), [0, 5, 10, 15]);
});

test("a zero-width domain yields a single tick", () => {
  assert.deepEqual(S.ticks(4, 4, 5), [4]);
});

test("floating point does not leak into tick values", () => {
  for (const value of S.ticks(0, 3, 5)) {
    assert.equal(value, Number(value.toFixed(10)));
  }
});

test("extent reads min and max through an accessor", () => {
  const rows = [{ v: 3 }, { v: -1 }, { v: 9 }];
  assert.deepEqual(S.extent(rows, (r) => r.v), [-1, 9]);
});

test("extent of nothing is a zero range", () => {
  assert.deepEqual(S.extent([], (r) => r.v), [0, 0]);
});

test("bar path is square at the baseline and rounded at the data end", () => {
  const d = S.roundedBarPath(10, 0, 100, 12, 4);
  assert.ok(d.startsWith("M10,0"), d);
  assert.ok(d.includes("A4,4"), d);
  assert.ok(d.trim().endsWith("Z"), d);
});

test("a bar shorter than the corner radius does not invert", () => {
  const d = S.roundedBarPath(0, 0, 2, 12, 4);
  assert.ok(!d.includes("NaN"), d);
  assert.ok(!/-\d/.test(d.replace("M0,0", "")), d);
});

test("region colour is assigned by name, never by rank", () => {
  const regions = ["Europe", "Asia", "Africa"];
  const first = S.regionColorVar("Asia", regions);
  const afterFilter = S.regionColorVar("Asia", ["Asia", "Europe"]);
  assert.equal(first, afterFilter);
});

test("every one of the seven regions gets a distinct slot", () => {
  const regions = [
    "Africa", "Asia", "Europe", "Middle East",
    "North America", "Oceania", "South America",
  ];
  const seen = new Set(regions.map((r) => S.regionColorVar(r, regions)));
  assert.equal(seen.size, 7);
});

test("slot list is the seven validated categorical slots", () => {
  assert.equal(S.REGION_SLOTS.length, 7);
  assert.deepEqual(S.REGION_SLOTS.slice(0, 2), ["--series-1", "--series-2"]);
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `node --test tests/js/core.test.mjs`
Expected: FAIL — `ENOENT` on `core.js`

- [ ] **Step 4: Write the implementation**

Create `analysis/dashboard_assets/js/core.js`:

```js
/* core.js — formatting, scales, ticks, and the region colour contract. */
(function (S) {
  "use strict";

  const NF0 = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
  const NF1 = new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 1, maximumFractionDigits: 1,
  });
  const NF2 = new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  });

  S.fmtInt = (n) => NF0.format(n);
  S.fmt1 = (n) => NF1.format(n);
  S.fmt2 = (n) => NF2.format(n);

  S.fmtCompact = function (n) {
    const abs = Math.abs(n);
    if (abs >= 1e6) return (n / 1e6).toFixed(1) + "M";
    if (abs >= 1e5) return Math.round(n / 1e3) + "K";
    return NF0.format(n);
  };

  S.linear = function (d0, d1, r0, r1) {
    const span = d1 - d0;
    const slope = span === 0 ? 0 : (r1 - r0) / span;
    return (v) => r0 + (v - d0) * slope;
  };

  S.niceStep = function (raw) {
    if (!(raw > 0)) return 1;
    const magnitude = Math.pow(10, Math.floor(Math.log10(raw)));
    const norm = raw / magnitude;
    const step = norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 5 ? 5 : 10;
    return step * magnitude;
  };

  S.ticks = function (min, max, count) {
    if (!(max > min)) return [min];
    const step = S.niceStep((max - min) / Math.max(1, count));
    const decimals = Math.max(0, -Math.floor(Math.log10(step)) + 1);
    const out = [];
    for (let i = Math.ceil(min / step); i * step <= max + step * 1e-9; i += 1) {
      out.push(Number((i * step).toFixed(decimals)));
    }
    return out;
  };

  S.extent = function (rows, accessor) {
    if (!rows.length) return [0, 0];
    let lo = Infinity;
    let hi = -Infinity;
    for (const row of rows) {
      const v = accessor(row);
      if (v < lo) lo = v;
      if (v > hi) hi = v;
    }
    return [lo, hi];
  };

  S.roundedBarPath = function (x, y, w, h, r) {
    const radius = Math.max(0, Math.min(r, w, h / 2));
    const end = x + w;
    return [
      "M" + x + "," + y,
      "H" + (end - radius),
      "A" + radius + "," + radius + " 0 0 1 " + end + "," + (y + radius),
      "V" + (y + h - radius),
      "A" + radius + "," + radius + " 0 0 1 " + (end - radius) + "," + (y + h),
      "H" + x,
      "Z",
    ].join(" ");
  };

  S.REGION_SLOTS = [
    "--series-1", "--series-2", "--series-3", "--series-4",
    "--series-5", "--series-6", "--series-7",
  ];

  // Colour follows the entity. The slot comes from the region's position in the
  // alphabetical list of ALL regions, so filtering never repaints a survivor.
  S.regionColorVar = function (region, allRegions) {
    const names = Array.from(new Set(allRegions)).sort();
    const index = names.indexOf(region);
    const slot = S.REGION_SLOTS[index < 0 ? 0 : index % S.REGION_SLOTS.length];
    return "var(" + slot + ")";
  };
})(globalThis.SOLAR);
```

`regionColorVar` takes the *full* region list from the payload, never the filtered list — `app.js` passes `payload.regions.map(r => r.region)` every time.

- [ ] **Step 5: Run test to verify it passes**

Run: `node --test tests/js/core.test.mjs`
Expected: 17 pass, 0 fail

- [ ] **Step 6: Register the asset**

In `analysis/build_dashboard.py`, append `"js/core.js"` to `ASSET_ORDER`:

```python
ASSET_ORDER = (
    "css/dashboard.css",
    "js/boot.js",
    "js/core.js",
)
```

- [ ] **Step 7: Bridge the JS suite into pytest**

Create `tests/test_dashboard_js.py`:

```python
"""Run the JavaScript suite from pytest so one command covers both languages."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
# A glob, not a directory: node 22 treats a bare directory argument as a module
# to execute rather than as a discovery root.
JS_TESTS = "tests/js/*.test.mjs"


def test_node_is_available():
    if shutil.which("node") is None:
        pytest.skip("node not installed — JS chart geometry is unverified here")


def test_javascript_suite_passes():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed — JS chart geometry is unverified here")

    result = subprocess.run(
        [node, "--test", JS_TESTS],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
    assert result.returncode == 0, "node --test failed; output above"
```

The skip is deliberate and narrow: a machine without node still runs the Python suite, and the skip message says exactly what went unverified.

- [ ] **Step 8: Run both suites**

Run: `python -m pytest tests/ -q`
Expected: all pass, 2 new tests in `test_dashboard_js.py`

Run: `node --test "tests/js/*.test.mjs"`
Expected: 17 pass

- [ ] **Step 9: Commit**

```bash
git add analysis/dashboard_assets/js/core.js analysis/build_dashboard.py tests/js tests/test_dashboard_js.py
git -c user.name="chinm" -c user.email="mishraswagat2804@gmail.com" commit -m "feat: add JS core scales and formatters with node test bridge"
```

---

### Task 3: Client-side rollups that reconcile against Python

**Files:**
- Create: `analysis/dashboard_assets/js/rollup.js`
- Modify: `analysis/build_dashboard.py` (`ASSET_ORDER`)
- Create: `tests/js/rollup.test.mjs`

**Interfaces:**
- Consumes: `SOLAR.extent` etc. from `core.js`; city records exactly as `analysis/aggregate.py` emits them
- Produces, all on `SOLAR`:
  - `round2(v) -> number`
  - `groupBy(rows, keyFn) -> Map<string, rows[]>`
  - `consistencyOf(values) -> number | null` — `1 − σ/μ`, sample σ (`n − 1`), clamped `[0, 1]`, `null` under 3 values
  - `denseRankDesc(entries) -> Map<string, number>` — `entries` is `[name, value][]`
  - `riskCountsOf(cities) -> {Low, Medium, High}`
  - `regionRollup(cities) -> rows` — same keys and order rule as `data.regions`
  - `countryRollup(cities) -> rows` — same keys and order rule as `data.countries`
  - `totalsOf(cities) -> {cities, countries, regions, co2_tons, installations, production_kwh}`

Why this module exists: a payback-risk filter changes which cities are in a region, so region totals must be recomputed in the browser. Duplicated aggregation logic is a divergence risk, so the tests below assert that the JS rollups over the **unfiltered** city list equal the Python-emitted `regions` and `countries` arrays. Verified beforehand: summing the display-rounded city `co2_tons` reproduces every region total, every country total and the grand total with **zero** drift, so the CO₂ comparisons are exact rather than tolerant. Means and consistency compare at `0.011` only to absorb a Python/JavaScript disagreement on exact half-way ties, which this dataset does not currently contain.

`riskCountsOf` counts the `risk_band` string that Python already put on each city record. It does not re-derive the band — one classifier, in `analysis/metrics.py`, is the whole point.

- [ ] **Step 1: Write the failing test**

Create `tests/js/rollup.test.mjs`:

```js
import test from "node:test";
import assert from "node:assert/strict";
import { load, payload } from "./load.mjs";

const S = load("boot.js", "core.js", "rollup.js");
const data = payload();

const close = (actual, expected, tol, what) =>
  assert.ok(
    Math.abs(actual - expected) <= tol,
    `${what}: ${actual} vs ${expected} (tol ${tol})`
  );

test("round2 keeps two decimals", () => {
  assert.equal(S.round2(26.6449), 26.64);
  assert.equal(S.round2(5), 5);
});

test("groupBy partitions without losing rows", () => {
  const groups = S.groupBy(data.cities, (c) => c.region);
  assert.equal(groups.size, 7);
  let total = 0;
  for (const rows of groups.values()) total += rows.length;
  assert.equal(total, 48);
});

test("consistency is null below three values", () => {
  assert.equal(S.consistencyOf([10000]), null);
  assert.equal(S.consistencyOf([10000, 12000]), null);
});

test("three identical values are genuine perfect consistency", () => {
  assert.equal(S.consistencyOf([10000, 10000, 10000]), 1);
});

test("extreme spread clamps at zero rather than going negative", () => {
  assert.equal(S.consistencyOf([1, 1, 100000]), 0);
});

test("dense rank shares a rank without skipping the next", () => {
  const ranks = S.denseRankDesc([["A", 10], ["B", 10], ["C", 5]]);
  assert.equal(ranks.get("A"), 1);
  assert.equal(ranks.get("B"), 1);
  assert.equal(ranks.get("C"), 2);
});

test("risk counts always carry all three bands", () => {
  const counts = S.riskCountsOf([{ risk_band: "Low" }, { risk_band: "Low" }]);
  assert.deepEqual(counts, { Low: 2, Medium: 0, High: 0 });
});

test("global risk counts match the verified distribution", () => {
  assert.deepEqual(S.riskCountsOf(data.cities), { Low: 5, Medium: 19, High: 24 });
});

test("totals reproduce the Python totals block", () => {
  const t = S.totalsOf(data.cities);
  assert.equal(t.cities, 48);
  assert.equal(t.countries, 30);
  assert.equal(t.regions, 7);
  assert.equal(t.installations, data.totals.installations);
  assert.equal(t.production_kwh, data.totals.production_kwh);
  close(t.co2_tons, data.totals.co2_tons, 1e-9, "totals co2");
});

test("region rollup equals the Python region records field for field", () => {
  const rolled = S.regionRollup(data.cities);
  assert.equal(rolled.length, data.regions.length);
  for (let i = 0; i < rolled.length; i += 1) {
    const got = rolled[i];
    const want = data.regions[i];
    assert.equal(got.region, want.region, "region order");
    assert.equal(got.cities, want.cities);
    assert.equal(got.rank, want.rank);
    assert.equal(got.installations, want.installations);
    assert.equal(got.production_kwh, want.production_kwh);
    assert.equal(got.small_sample, want.small_sample);
    assert.deepEqual(got.risk_counts, want.risk_counts);
    close(got.co2_tons, want.co2_tons, 1e-9, want.region + " co2");
    close(got.mean_roi, want.mean_roi, 0.011, want.region + " mean roi");
    if (want.consistency === null) {
      assert.equal(got.consistency, null, want.region + " consistency");
    } else {
      close(got.consistency, want.consistency, 0.011, want.region + " consistency");
    }
  }
});

test("region rollup is ordered by rank, best first", () => {
  const rolled = S.regionRollup(data.cities);
  assert.equal(rolled[0].region, "Middle East");
  assert.deepEqual(
    rolled.map((r) => r.rank),
    rolled.map((r) => r.rank).slice().sort((a, b) => a - b)
  );
});

test("country rollup equals the Python country records field for field", () => {
  const rolled = S.countryRollup(data.cities);
  assert.equal(rolled.length, data.countries.length);
  for (let i = 0; i < rolled.length; i += 1) {
    const got = rolled[i];
    const want = data.countries[i];
    assert.equal(got.country, want.country, "country order");
    assert.equal(got.region, want.region);
    assert.equal(got.cities, want.cities);
    assert.equal(got.installations, want.installations);
    close(got.co2_tons, want.co2_tons, 1e-9, want.country + " co2");
    close(got.mean_roi, want.mean_roi, 0.011, want.country + " mean roi");
    close(
      got.mean_production_kwh,
      want.mean_production_kwh,
      0.011,
      want.country + " mean production"
    );
  }
});

test("Dubai survives every client-side rollup", () => {
  // The same defect the reference dashboard shipped, guarded on this side too.
  const asia = S.regionRollup(data.cities).find((r) => r.region === "Asia");
  close(asia.co2_tons, 54.72, 1e-9, "Asia co2 including Dubai");
  assert.equal(asia.installations, 1469100);
  const uae = S.countryRollup(data.cities).find((r) => r.country === "UAE");
  close(uae.co2_tons, 6.3, 1e-9, "UAE co2");
  assert.equal(uae.installations, 850);
});

test("filtering to one region still reconciles inside that region", () => {
  const oceania = data.cities.filter((c) => c.region === "Oceania");
  const rolled = S.regionRollup(oceania);
  assert.equal(rolled.length, 1);
  assert.equal(rolled[0].cities, 3);
  assert.equal(rolled[0].rank, 1, "rank is relative to the filtered slice");
  close(
    rolled[0].co2_tons,
    oceania.reduce((sum, c) => sum + c.co2_tons, 0),
    1e-9,
    "Oceania co2"
  );
});

test("an empty selection rolls up to nothing, not to NaN", () => {
  assert.deepEqual(S.regionRollup([]), []);
  assert.deepEqual(S.countryRollup([]), []);
  const t = S.totalsOf([]);
  assert.equal(t.cities, 0);
  assert.equal(t.co2_tons, 0);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/js/rollup.test.mjs`
Expected: FAIL — `ENOENT` on `rollup.js`

- [ ] **Step 3: Write the implementation**

Create `analysis/dashboard_assets/js/rollup.js`:

```js
/* rollup.js — region/country/total rollups, mirroring analysis/aggregate.py.
   A payback-risk filter changes a region's membership, so these totals cannot
   be read off the payload; they are recomputed from the filtered city list.
   tests/js/rollup.test.mjs asserts this agrees with the Python output. */
(function (S) {
  "use strict";

  const MIN_CITIES_FOR_CONSISTENCY = 3;
  const SMALL_SAMPLE_MAX = 5;
  const BANDS = ["Low", "Medium", "High"];

  S.round2 = (v) => Math.round((v + Number.EPSILON) * 100) / 100;

  S.groupBy = function (rows, keyFn) {
    const groups = new Map();
    for (const row of rows) {
      const key = keyFn(row);
      const bucket = groups.get(key);
      if (bucket) bucket.push(row);
      else groups.set(key, [row]);
    }
    return groups;
  };

  const sum = (rows, accessor) => rows.reduce((acc, row) => acc + accessor(row), 0);
  const mean = (rows, accessor) => (rows.length ? sum(rows, accessor) / rows.length : 0);

  S.consistencyOf = function (values) {
    if (values.length < MIN_CITIES_FOR_CONSISTENCY) return null;
    const mu = values.reduce((a, b) => a + b, 0) / values.length;
    if (mu === 0) return null;
    const variance =
      values.reduce((acc, v) => acc + (v - mu) * (v - mu), 0) / (values.length - 1);
    const cv = Math.sqrt(variance) / mu;
    return Math.max(0, Math.min(1, 1 - cv));
  };

  S.denseRankDesc = function (entries) {
    const distinct = Array.from(new Set(entries.map(([, v]) => v))).sort((a, b) => b - a);
    const rankOf = new Map(distinct.map((v, i) => [v, i + 1]));
    return new Map(entries.map(([name, v]) => [name, rankOf.get(v)]));
  };

  S.riskCountsOf = function (cities) {
    const counts = { Low: 0, Medium: 0, High: 0 };
    for (const city of cities) {
      if (BANDS.indexOf(city.risk_band) >= 0) counts[city.risk_band] += 1;
    }
    return counts;
  };

  S.totalsOf = function (cities) {
    return {
      cities: cities.length,
      countries: new Set(cities.map((c) => c.country)).size,
      regions: new Set(cities.map((c) => c.region)).size,
      co2_tons: S.round2(sum(cities, (c) => c.co2_tons)),
      installations: sum(cities, (c) => c.installations),
      production_kwh: sum(cities, (c) => c.production_kwh),
    };
  };

  S.regionRollup = function (cities) {
    const groups = S.groupBy(cities, (c) => c.region);
    const means = Array.from(groups, ([region, rows]) => [region, mean(rows, (c) => c.roi_pct)]);
    const ranks = S.denseRankDesc(means);

    const records = Array.from(groups, ([region, rows]) => ({
      region: region,
      cities: rows.length,
      rank: ranks.get(region),
      mean_roi: S.round2(mean(rows, (c) => c.roi_pct)),
      co2_tons: S.round2(sum(rows, (c) => c.co2_tons)),
      installations: sum(rows, (c) => c.installations),
      production_kwh: sum(rows, (c) => c.production_kwh),
      consistency: (function () {
        const value = S.consistencyOf(rows.map((c) => c.production_kwh));
        return value === null ? null : S.round2(value);
      })(),
      small_sample: rows.length < SMALL_SAMPLE_MAX,
      risk_counts: S.riskCountsOf(rows),
    }));

    records.sort((a, b) => a.rank - b.rank || a.region.localeCompare(b.region));
    return records;
  };

  S.countryRollup = function (cities) {
    const groups = S.groupBy(cities, (c) => c.country);
    const records = Array.from(groups, ([country, rows]) => ({
      country: country,
      region: rows[0].region,
      cities: rows.length,
      mean_roi: S.round2(mean(rows, (c) => c.roi_pct)),
      mean_production_kwh: S.round2(mean(rows, (c) => c.production_kwh)),
      co2_tons: S.round2(sum(rows, (c) => c.co2_tons)),
      installations: sum(rows, (c) => c.installations),
      _co2: sum(rows, (c) => c.co2_tons),
    }));

    // Sort on the unrounded total, exactly as country_records does.
    records.sort((a, b) => b._co2 - a._co2 || a.country.localeCompare(b.country));
    for (const record of records) delete record._co2;
    return records;
  };
})(globalThis.SOLAR);
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test tests/js/rollup.test.mjs`
Expected: 15 pass, 0 fail

If the region- or country-order assertions fail, the cause is a tie broken differently by `localeCompare` versus Python's string sort — fix the JS comparator, never the Python side; `data.json` is the reference.

- [ ] **Step 5: Register the asset**

In `analysis/build_dashboard.py`, append `"js/rollup.js"` to `ASSET_ORDER` after `"js/core.js"`.

- [ ] **Step 6: Run the whole suite**

Run: `python -m pytest tests/ -q` — all pass
Run: `node --test "tests/js/*.test.mjs"` — 32 pass

- [ ] **Step 7: Commit**

```bash
git add analysis/dashboard_assets/js/rollup.js analysis/build_dashboard.py tests/js/rollup.test.mjs
git -c user.name="chinm" -c user.email="mishraswagat2804@gmail.com" commit -m "feat: add client-side rollups reconciled against the Python output"
```

---

### Task 4: Filter state, chips, and the page skeleton

**Files:**
- Create: `analysis/dashboard_assets/js/filters.js`
- Create: `analysis/dashboard_assets/js/render.js`
- Create: `analysis/dashboard_assets/js/app.js`
- Modify: `analysis/build_dashboard.py` (`ASSET_ORDER`)
- Create: `tests/js/fakedom.mjs`
- Create: `tests/js/filters.test.mjs`
- Create: `tests/js/app.test.mjs`
- Modify: `tests/test_build.py` (assert the new assets are inlined)

**Interfaces:**
- Consumes: `SOLAR.regionColorVar`, `SOLAR.regionRollup`, `SOLAR.totalsOf`, `SOLAR.fmt*`
- Produces on `SOLAR`:
  - `PAGES = [{id, tabId, label}, …]` — `financial`, `production`, `sustainability`
  - `initialState(payload) -> {regions: string[], bands: string[], page: string}` — arrays, sorted, all selected
  - `toggleValue(selected, value, all) -> string[]` — remove if present, add if absent; **emptying restores all**
  - `isolateValue(selected, value, all) -> string[]` — narrow to one; calling it again on an already-isolated value restores all
  - `filterCities(cities, state) -> rows`
  - `describeFilter(cities, filtered, state, allRegions, allBands) -> string`
  - `el(tag, attrs, children) -> Element`, `svgEl(tag, attrs, children) -> Element`, `clear(node)`
  - `register(chart)` / `SOLAR.charts` — a chart is `{id, page, title, definition, wide, callout, render(container, ctx), table(ctx)}`
  - `buildContext(payload, state) -> ctx` — `{payload, state, cities, regions, countries, totals, allRegions, allBands}`
  - `mount(doc) -> api` — builds chrome, renders every registered chart, returns `{getState, setState, ctx}` for tests

`render` and `table` are both optional on a chart: `render` draws SVG into the container, `table` returns `{caption, columns, rows}` for the table-view twin. Later tasks add charts; this task ships the machinery plus zero charts, and the page must still assemble cleanly.

- [ ] **Step 1: Write the DOM shim**

Create `tests/js/fakedom.mjs`. It implements only what the render layer uses — enough to prove the page assembles, not a browser.

```js
/* fakedom.mjs — the smallest document the dashboard actually needs. */

class ClassList {
  constructor() { this.items = new Set(); }
  add(...names) { names.forEach((n) => this.items.add(n)); }
  remove(...names) { names.forEach((n) => this.items.delete(n)); }
  contains(name) { return this.items.has(name); }
  toString() { return Array.from(this.items).join(" "); }
}

class Element {
  constructor(doc, tag, ns) {
    this.ownerDocument = doc;
    this.tagName = tag.toUpperCase();
    this.localName = tag;
    this.namespaceURI = ns || null;
    this.attributes = {};
    this.childNodes = [];
    this.parentNode = null;
    this.classList = new ClassList();
    this.dataset = {};
    this.style = {};
    this.listeners = {};
    this.hidden = false;
    this._text = "";
  }

  setAttribute(name, value) {
    this.attributes[name] = String(value);
    if (name === "id") this.ownerDocument.index(this);
    if (name === "class") {
      this.classList = new ClassList();
      this.classList.add(...String(value).split(/\s+/).filter(Boolean));
    }
  }

  getAttribute(name) {
    return Object.prototype.hasOwnProperty.call(this.attributes, name)
      ? this.attributes[name]
      : null;
  }

  appendChild(child) {
    child.parentNode = this;
    this.childNodes.push(child);
    return child;
  }

  append(...children) { children.forEach((c) => this.appendChild(c)); }

  replaceChildren(...children) {
    this.childNodes = [];
    this._text = "";
    children.forEach((c) => this.appendChild(c));
  }

  addEventListener(type, handler) {
    (this.listeners[type] = this.listeners[type] || []).push(handler);
  }

  dispatch(type, event) {
    for (const handler of this.listeners[type] || []) handler(event || { target: this });
  }

  set textContent(value) { this._text = String(value); this.childNodes = []; }

  get textContent() {
    return this._text + this.childNodes.map((c) => c.textContent).join("");
  }

  descendants() {
    return this.childNodes.flatMap((c) => [c, ...c.descendants()]);
  }

  matches(selector) {
    if (selector.startsWith("#")) return this.attributes.id === selector.slice(1);
    if (selector.startsWith(".")) return this.classList.contains(selector.slice(1));
    if (selector.startsWith("[")) {
      const [name, raw] = selector.slice(1, -1).split("=");
      if (raw === undefined) return this.getAttribute(name) !== null;
      return this.getAttribute(name) === raw.replace(/["']/g, "");
    }
    return this.localName === selector;
  }

  querySelectorAll(selector) {
    return this.descendants().filter((node) => node.matches(selector));
  }

  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
}

class FakeDocument {
  constructor() {
    this.byId = new Map();
    this.documentElement = new Element(this, "html");
    this.body = new Element(this, "body");
    this.documentElement.appendChild(this.body);
  }
  index(el) { this.byId.set(el.attributes.id, el); }
  createElement(tag) { return new Element(this, tag); }
  createElementNS(ns, tag) { return new Element(this, tag, ns); }
  getElementById(id) { return this.byId.get(id) || null; }
  querySelectorAll(selector) { return this.documentElement.querySelectorAll(selector); }
  querySelector(selector) { return this.documentElement.querySelector(selector); }
}

const CHROME_IDS = [
  "app", "kpis", "tabs", "filters", "region-chips", "risk-chips",
  "reset-filters", "toggle-tables", "filter-readout", "theme-toggle",
  "page-financial", "page-production", "page-sustainability",
  "caveats", "meta", "solar-data",
];

/** A document carrying the same ids as shell.html, plus the payload block. */
export function makeDocument(payload) {
  const doc = new FakeDocument();
  for (const id of CHROME_IDS) {
    const el = doc.createElement(id.startsWith("page-") ? "section" : "div");
    el.setAttribute("id", id);
    if (id.startsWith("page-") && id !== "page-financial") el.hidden = true;
    doc.body.appendChild(el);
  }
  doc.getElementById("solar-data").textContent = JSON.stringify(payload);
  for (const page of ["financial", "production", "sustainability"]) {
    const tab = doc.createElement("button");
    tab.setAttribute("id", "tab-" + page);
    tab.setAttribute("aria-controls", "page-" + page);
    tab.setAttribute("aria-selected", page === "financial" ? "true" : "false");
    doc.getElementById("tabs").appendChild(tab);
  }
  return doc;
}
```

- [ ] **Step 2: Write the failing filter test**

Create `tests/js/filters.test.mjs`:

```js
import test from "node:test";
import assert from "node:assert/strict";
import { load, payload } from "./load.mjs";

const S = load("boot.js", "core.js", "rollup.js", "filters.js");
const data = payload();

const REGIONS = Array.from(new Set(data.cities.map((c) => c.region))).sort();
const BANDS = ["Low", "Medium", "High"];

test("the initial state selects everything", () => {
  const state = S.initialState(data);
  assert.deepEqual(state.regions, REGIONS);
  assert.deepEqual(state.bands, BANDS);
  assert.equal(state.page, "financial");
  assert.equal(S.filterCities(data.cities, state).length, 48);
});

test("toggling a value off removes only that value", () => {
  const next = S.toggleValue(REGIONS, "Europe", REGIONS);
  assert.ok(!next.includes("Europe"));
  assert.equal(next.length, REGIONS.length - 1);
});

test("toggling the same value back on restores it", () => {
  const off = S.toggleValue(REGIONS, "Europe", REGIONS);
  const on = S.toggleValue(off, "Europe", REGIONS);
  assert.deepEqual(on, REGIONS);
});

test("emptying the selection restores all rather than blanking the page", () => {
  const next = S.toggleValue(["Europe"], "Europe", REGIONS);
  assert.deepEqual(next, REGIONS);
});

test("isolate narrows to a single value", () => {
  assert.deepEqual(S.isolateValue(REGIONS, "Asia", REGIONS), ["Asia"]);
});

test("isolating an already-isolated value restores all", () => {
  assert.deepEqual(S.isolateValue(["Asia"], "Asia", REGIONS), REGIONS);
});

test("region filtering keeps the right cities", () => {
  const state = { ...S.initialState(data), regions: ["Oceania"] };
  const rows = S.filterCities(data.cities, state);
  assert.equal(rows.length, 3);
  assert.ok(rows.every((c) => c.region === "Oceania"));
});

test("risk filtering keeps the right cities", () => {
  const state = { ...S.initialState(data), bands: ["Low"] };
  assert.equal(S.filterCities(data.cities, state).length, 5);
});

test("region and risk filters intersect", () => {
  const state = { ...S.initialState(data), regions: ["Asia"], bands: ["Low"] };
  const rows = S.filterCities(data.cities, state);
  assert.ok(rows.every((c) => c.region === "Asia" && c.risk_band === "Low"));
  assert.ok(rows.some((c) => c.city === "Dubai"), "Dubai is Asia and Low");
});

test("a filter that matches nothing yields an empty list, not an error", () => {
  const state = { ...S.initialState(data), regions: ["Middle East"], bands: ["High"] };
  assert.deepEqual(S.filterCities(data.cities, state), []);
});

test("the readout names the slice in plain words", () => {
  const state = S.initialState(data);
  const all = S.describeFilter(data.cities, data.cities, state, REGIONS, BANDS);
  assert.match(all, /48 of 48 cities/);
  assert.match(all, /all regions/);

  const narrowed = { ...state, regions: ["Asia"] };
  const rows = S.filterCities(data.cities, narrowed);
  const text = S.describeFilter(data.cities, rows, narrowed, REGIONS, BANDS);
  assert.match(text, /12 of 48 cities/);
  assert.match(text, /Asia/);
});
```

- [ ] **Step 3: Write the failing app test**

Create `tests/js/app.test.mjs`:

```js
import test from "node:test";
import assert from "node:assert/strict";
import { load, payload } from "./load.mjs";
import { makeDocument } from "./fakedom.mjs";

const S = load("boot.js", "core.js", "rollup.js", "filters.js", "render.js", "app.js");
const data = payload();

const mountFresh = () => {
  S.charts.length = 0;
  return { doc: makeDocument(data), api: null };
};

test("mount fills the KPI strip from the payload", () => {
  const { doc } = mountFresh();
  S.mount(doc);
  const values = doc
    .getElementById("kpis")
    .querySelectorAll(".kpi-value")
    .map((n) => n.textContent);
  assert.ok(values.includes("48"), values.join(" | "));
  assert.ok(values.some((v) => v.includes("208.35")), values.join(" | "));
});

test("mount renders one chip per region plus one per risk band", () => {
  const { doc } = mountFresh();
  S.mount(doc);
  assert.equal(doc.getElementById("region-chips").querySelectorAll(".chip").length, 7);
  assert.equal(doc.getElementById("risk-chips").querySelectorAll(".chip").length, 3);
});

test("every chip starts selected", () => {
  const { doc } = mountFresh();
  S.mount(doc);
  const chips = doc.getElementById("region-chips").querySelectorAll(".chip");
  assert.ok(chips.every((c) => c.getAttribute("data-selected") === "true"));
});

test("region chips carry a colour key that does not depend on the filter", () => {
  const { doc } = mountFresh();
  const api = S.mount(doc);
  const keyFor = (d) =>
    d.getElementById("region-chips")
      .querySelectorAll(".chip")
      .find((c) => c.textContent.includes("Asia"))
      .querySelector(".chip-key")
      .getAttribute("style");

  const before = keyFor(doc);
  api.setState({ ...api.getState(), regions: ["Asia", "Europe"] });
  assert.equal(keyFor(doc), before, "Asia must keep its hue when others are filtered out");
});

test("mount renders the five caveats", () => {
  const { doc } = mountFresh();
  S.mount(doc);
  assert.equal(doc.getElementById("caveats").querySelectorAll("li").length, 5);
});

test("mount writes the source and generation metadata", () => {
  const { doc } = mountFresh();
  S.mount(doc);
  assert.match(doc.getElementById("meta").textContent, /solar_energy_worldwide\.csv/);
});

test("the readout reports the unfiltered slice on load", () => {
  const { doc } = mountFresh();
  S.mount(doc);
  assert.match(doc.getElementById("filter-readout").textContent, /48 of 48 cities/);
});

test("setState re-renders the readout and the KPI strip", () => {
  const { doc } = mountFresh();
  const api = S.mount(doc);
  api.setState({ ...api.getState(), regions: ["Oceania"] });
  assert.match(doc.getElementById("filter-readout").textContent, /3 of 48 cities/);
  const values = doc
    .getElementById("kpis")
    .querySelectorAll(".kpi-value")
    .map((n) => n.textContent);
  assert.ok(values.includes("3"), values.join(" | "));
});

test("a registered chart gets a card with a title and a definition", () => {
  const { doc } = mountFresh();
  let seen = null;
  S.register({
    id: "probe",
    page: "financial",
    title: "Probe chart",
    definition: "A test measure, defined here.",
    render(container, ctx) { seen = ctx.cities.length; container.appendChild(S.el("g")); },
  });
  S.mount(doc);
  const card = doc.getElementById("page-financial").querySelector(".card");
  assert.ok(card, "card not created");
  assert.match(card.textContent, /Probe chart/);
  assert.match(card.textContent, /A test measure, defined here\./);
  assert.equal(seen, 48);
});

test("a chart re-renders against the filtered slice", () => {
  const { doc } = mountFresh();
  const counts = [];
  S.register({
    id: "probe",
    page: "financial",
    title: "Probe chart",
    definition: "Counts rows.",
    render(container, ctx) { counts.push(ctx.cities.length); },
  });
  const api = S.mount(doc);
  api.setState({ ...api.getState(), bands: ["Low"] });
  assert.deepEqual(counts, [48, 5]);
});

test("charts land on the page they declare", () => {
  const { doc } = mountFresh();
  S.register({ id: "a", page: "production", title: "A", definition: "d", render() {} });
  S.register({ id: "b", page: "sustainability", title: "B", definition: "d", render() {} });
  S.mount(doc);
  assert.equal(doc.getElementById("page-financial").querySelectorAll(".card").length, 0);
  assert.equal(doc.getElementById("page-production").querySelectorAll(".card").length, 1);
  assert.equal(doc.getElementById("page-sustainability").querySelectorAll(".card").length, 1);
});

test("the table twin is built from the chart's own rows", () => {
  const { doc } = mountFresh();
  S.register({
    id: "probe",
    page: "financial",
    title: "Probe",
    definition: "d",
    render() {},
    table(ctx) {
      return {
        caption: "Every city",
        columns: ["City", "ROI %"],
        rows: ctx.cities.map((c) => [c.city, S.fmt1(c.roi_pct)]),
      };
    },
  });
  S.mount(doc);
  const table = doc.getElementById("page-financial").querySelector(".values");
  assert.ok(table, "table twin not built");
  assert.equal(table.querySelectorAll("tbody").length, 1);
  assert.equal(table.querySelector("tbody").querySelectorAll("tr").length, 48);
});

test("mount survives a page with no registered charts", () => {
  const { doc } = mountFresh();
  assert.doesNotThrow(() => S.mount(doc));
});
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `node --test tests/js/filters.test.mjs tests/js/app.test.mjs`
Expected: FAIL — `ENOENT` on `filters.js`

- [ ] **Step 5: Write the filter module**

Create `analysis/dashboard_assets/js/filters.js`:

```js
/* filters.js — pure filter state. No DOM, no side effects. */
(function (S) {
  "use strict";

  S.BANDS = ["Low", "Medium", "High"];

  S.PAGES = [
    { id: "financial", tabId: "tab-financial", label: "Financial performance" },
    { id: "production", tabId: "tab-production", label: "Production" },
    { id: "sustainability", tabId: "tab-sustainability", label: "Sustainability" },
  ];

  S.allRegionsOf = (payload) =>
    Array.from(new Set(payload.cities.map((c) => c.region))).sort();

  S.initialState = function (payload) {
    return {
      regions: S.allRegionsOf(payload),
      bands: S.BANDS.slice(),
      page: "financial",
    };
  };

  const order = (values, all) => all.filter((v) => values.indexOf(v) >= 0);

  S.toggleValue = function (selected, value, all) {
    const next = selected.indexOf(value) >= 0
      ? selected.filter((v) => v !== value)
      : selected.concat([value]);
    // An empty selection would render an empty dashboard, which reads as a bug
    // rather than a choice. Clearing the last chip means "show everything".
    return next.length ? order(next, all) : all.slice();
  };

  S.isolateValue = function (selected, value, all) {
    const isolated = selected.length === 1 && selected[0] === value;
    return isolated ? all.slice() : [value];
  };

  S.filterCities = function (cities, state) {
    return cities.filter(
      (c) => state.regions.indexOf(c.region) >= 0 && state.bands.indexOf(c.risk_band) >= 0
    );
  };

  S.describeFilter = function (cities, filtered, state, allRegions, allBands) {
    const parts = [filtered.length + " of " + cities.length + " cities"];
    parts.push(
      state.regions.length === allRegions.length
        ? "all regions"
        : state.regions.join(", ")
    );
    parts.push(
      state.bands.length === allBands.length
        ? "all payback risk bands"
        : state.bands.join(", ") + " payback risk"
    );
    return parts.join(" · ");
  };
})(globalThis.SOLAR);
```

- [ ] **Step 6: Write the render helpers**

Create `analysis/dashboard_assets/js/render.js`. Later tasks extend this file with the SVG drawing helpers; this task ships the element factories and the table twin.

```js
/* render.js — element factories and the table-view twin.
   Text always goes in through textContent: series and city names come from a
   CSV and are treated as untrusted data. */
(function (S) {
  "use strict";

  const SVG_NS = "http://www.w3.org/2000/svg";

  function applyAttrs(node, attrs) {
    for (const name in attrs) {
      if (!Object.prototype.hasOwnProperty.call(attrs, name)) continue;
      const value = attrs[name];
      if (value === null || value === undefined || value === false) continue;
      if (name === "text") node.textContent = String(value);
      else node.setAttribute(name, value);
    }
  }

  function appendAll(node, children) {
    if (!children) return;
    for (const child of [].concat(children)) {
      if (child) node.appendChild(child);
    }
  }

  // The document is injected rather than read off globalThis, so the node
  // tests can mount the whole page against the shim in tests/js/fakedom.mjs.
  S._doc = null;
  S.useDocument = function (doc) { S._doc = doc; return doc; };
  S.doc = () => S._doc || globalThis.document;

  S.el = function (tag, attrs, children) {
    const node = S.doc().createElement(tag);
    applyAttrs(node, attrs || {});
    appendAll(node, children);
    return node;
  };

  S.svgEl = function (tag, attrs, children) {
    const node = S.doc().createElementNS(SVG_NS, tag);
    applyAttrs(node, attrs || {});
    appendAll(node, children);
    return node;
  };

  S.clear = function (node) {
    node.replaceChildren();
    return node;
  };

  S.buildTable = function (model) {
    const head = S.el("thead", null, [
      S.el("tr", null, model.columns.map((c) => S.el("th", { scope: "col", text: c }))),
    ]);
    const body = S.el("tbody", null,
      model.rows.map((row) =>
        S.el("tr", null, row.map((cell, i) =>
          S.el(i === 0 ? "th" : "td", i === 0 ? { scope: "row", text: cell } : { text: cell })
        ))
      )
    );
    return S.el("table", { class: "values" }, [
      S.el("caption", { text: model.caption }),
      head,
      body,
    ]);
  };
})(globalThis.SOLAR);
```

- [ ] **Step 7: Write the app**

Create `analysis/dashboard_assets/js/app.js`:

```js
/* app.js — chrome, chart registry, and the single re-render path.
   Every state change goes through render(): one filter slice, one set of
   numbers, no chart holding a stale view. */
(function (S) {
  "use strict";

  S.charts = [];
  S.register = function (chart) { S.charts.push(chart); };

  S.buildContext = function (payload, state) {
    const cities = S.filterCities(payload.cities, state);
    return {
      payload: payload,
      state: state,
      cities: cities,
      regions: S.regionRollup(cities),
      countries: S.countryRollup(cities),
      totals: S.totalsOf(cities),
      allRegions: S.allRegionsOf(payload),
      allBands: S.BANDS,
    };
  };

  function kpiTile(value, label) {
    return S.el("div", { class: "kpi" }, [
      S.el("span", { class: "kpi-value", text: value }),
      S.el("span", { class: "kpi-label", text: label }),
    ]);
  }

  function renderKpis(doc, ctx) {
    const t = ctx.totals;
    S.clear(doc.getElementById("kpis")).append(
      kpiTile(S.fmtInt(t.cities), "Cities in view"),
      kpiTile(S.fmtInt(t.countries), "Countries"),
      kpiTile(S.fmt2(t.co2_tons), "Tonnes CO₂ avoided per year"),
      kpiTile(S.fmtCompact(t.installations), "Installations"),
      kpiTile(S.fmtCompact(t.production_kwh), "kWh produced per year")
    );
  }

  function chip(kind, value, selected, colorVar, onToggle) {
    const input = S.el("input", { type: "checkbox" });
    if (selected) input.setAttribute("checked", "checked");
    const key = colorVar
      ? S.el("span", { class: "chip-key", style: "background:" + colorVar })
      : null;
    const label = S.el("label", { class: "chip", "data-selected": String(selected) }, [
      input,
      S.el("span", { class: "chip-body" }, [
        S.el("span", { class: "chip-check", text: "✓" }),
        key,
        S.el("span", { text: value }),
      ]),
    ]);
    input.addEventListener("change", () => onToggle(kind, value));
    return label;
  }

  function renderChips(doc, ctx, onToggle) {
    const regionBox = S.clear(doc.getElementById("region-chips"));
    const regionChips = S.el("div", { class: "chips" });
    for (const region of ctx.allRegions) {
      regionChips.appendChild(
        chip(
          "regions",
          region,
          ctx.state.regions.indexOf(region) >= 0,
          S.regionColorVar(region, ctx.allRegions),
          onToggle
        )
      );
    }
    regionBox.appendChild(regionChips);

    const riskBox = S.clear(doc.getElementById("risk-chips"));
    const riskChips = S.el("div", { class: "chips" });
    for (const band of ctx.allBands) {
      riskChips.appendChild(
        chip("bands", band, ctx.state.bands.indexOf(band) >= 0, null, onToggle)
      );
    }
    riskBox.appendChild(riskChips);
  }

  function renderCharts(doc, ctx, showTables) {
    for (const page of S.PAGES) {
      const host = S.clear(doc.getElementById("page-" + page.id));
      for (const chart of S.charts.filter((c) => c.page === page.id)) {
        const plot = S.el("div", { class: "plot" });
        const card = S.el("figure", {
          class: "card" + (chart.wide ? " wide" : ""),
          "data-chart": chart.id,
        }, [
          S.el("figcaption", null, [
            S.el("h3", { text: chart.title }),
            S.el("p", { class: "definition", text: chart.definition }),
          ]),
          plot,
        ]);
        if (chart.render) chart.render(plot, ctx);
        if (chart.callout) {
          card.appendChild(S.el("p", { class: "callout", text: chart.callout(ctx) }));
        }
        if (chart.table) {
          const table = S.buildTable(chart.table(ctx));
          table.hidden = !showTables;
          card.appendChild(table);
        }
        host.appendChild(card);
      }
    }
  }

  function renderCaveats(doc, payload) {
    S.clear(doc.getElementById("caveats")).append(
      ...payload.caveats.map((text) => S.el("li", { text: text }))
    );
    doc.getElementById("meta").textContent =
      "Source: " + payload.meta.source +
      " · built " + payload.meta.generated_utc +
      " · spec " + payload.meta.spec;
  }

  function showPage(doc, pageId) {
    for (const page of S.PAGES) {
      const panel = doc.getElementById("page-" + page.id);
      const tab = doc.getElementById(page.tabId);
      const active = page.id === pageId;
      panel.hidden = !active;
      if (tab) tab.setAttribute("aria-selected", String(active));
    }
  }

  S.mount = function (document_) {
    const doc = S.useDocument(document_ || globalThis.document);
    const payload = S.readPayload(doc);
    let state = S.initialState(payload);
    let showTables = false;

    function onToggle(kind, value) {
      const all = kind === "regions" ? S.allRegionsOf(payload) : S.BANDS;
      setState(Object.assign({}, state, { [kind]: S.toggleValue(state[kind], value, all) }));
    }

    function render() {
      const ctx = S.buildContext(payload, state);
      ctx.isolate = (kind, value) => {
        const all = kind === "regions" ? S.allRegionsOf(payload) : S.BANDS;
        setState(Object.assign({}, state, {
          [kind]: S.isolateValue(state[kind], value, all),
        }));
      };
      renderKpis(doc, ctx);
      renderChips(doc, ctx, onToggle);
      renderCharts(doc, ctx, showTables);
      doc.getElementById("filter-readout").textContent = S.describeFilter(
        payload.cities, ctx.cities, state, ctx.allRegions, ctx.allBands
      );
      showPage(doc, state.page);
      return ctx;
    }

    function setState(next) { state = next; return render(); }

    const reset = doc.getElementById("reset-filters");
    if (reset) {
      reset.addEventListener("click", () =>
        setState(Object.assign({}, S.initialState(payload), { page: state.page }))
      );
    }

    const tables = doc.getElementById("toggle-tables");
    if (tables) {
      tables.addEventListener("change", () => { showTables = !showTables; render(); });
    }

    for (const page of S.PAGES) {
      const tab = doc.getElementById(page.tabId);
      if (tab) {
        tab.addEventListener("click", () =>
          setState(Object.assign({}, state, { page: page.id }))
        );
      }
    }

    const themeToggle = doc.getElementById("theme-toggle");
    if (themeToggle) {
      themeToggle.addEventListener("click", () => {
        const root = doc.documentElement;
        const dark = root.getAttribute("data-theme") === "dark";
        root.setAttribute("data-theme", dark ? "light" : "dark");
        themeToggle.setAttribute("aria-pressed", String(!dark));
        themeToggle.textContent = dark ? "Dark theme" : "Light theme";
      });
    }

    renderCaveats(doc, payload);
    const ctx = render();
    return { getState: () => state, setState: setState, ctx: ctx };
  };

  if (typeof globalThis.document !== "undefined" && globalThis.document.getElementById) {
    if (globalThis.document.getElementById("solar-data")) S.mount(globalThis.document);
  }
})(globalThis.SOLAR);
```

The auto-mount guard at the bottom is what makes the file work in a browser and stay inert under `node --test`, where there is no `document`.

- [ ] **Step 8: Run the tests to verify they pass**

Run: `node --test tests/js/filters.test.mjs tests/js/app.test.mjs`
Expected: 24 pass, 0 fail

- [ ] **Step 9: Register the assets and extend the Python test**

In `analysis/build_dashboard.py`, `ASSET_ORDER` becomes:

```python
ASSET_ORDER = (
    "css/dashboard.css",
    "js/boot.js",
    "js/core.js",
    "js/rollup.js",
    "js/filters.js",
    "js/render.js",
    "js/app.js",
)
```

`app.js` stays last for the rest of the plan — every chart module registers itself at load time and must be defined before `mount` runs.

Append to `tests/test_build.py`:

```python
def test_asset_order_ends_with_app_js():
    assert ASSET_ORDER[-1] == "js/app.js"


def test_chart_modules_load_before_the_app(html):
    assert html.index("S.mount = function") > html.index("S.filterCities = function")


def test_page_hosts_are_empty_in_the_emitted_html(html):
    # Cards are built at runtime from the registry; the shell ships them empty.
    start = html.index('id="page-financial"')
    end = html.index("</section>", start)
    assert "card" not in html[start:end]
```

- [ ] **Step 10: Run everything and open the page**

Run: `python -m pytest tests/ -q` — all pass
Run: `node --test "tests/js/*.test.mjs"` — 56 pass
Run: `python -m analysis.build_dashboard`

Open `output/dashboard.html`. Expected: KPI strip showing 48 / 30 / 208.35 / 2.3M / 520,875; seven region chips each with its own colour key and a check; three risk chips; tabs that switch the visible (empty) page; reset and table toggle present; five caveats in the footer; theme toggle flips light and dark.

- [ ] **Step 11: Commit**

```bash
git add analysis/dashboard_assets/js analysis/build_dashboard.py tests/js tests/test_build.py
git -c user.name="chinm" -c user.email="mishraswagat2804@gmail.com" commit -m "feat: add filter state, chip row, and the chart registry"
```

---

### Task 5: Bars — four ranked charts and the stacked risk chart

**Files:**
- Create: `analysis/dashboard_assets/js/charts_bars.js`
- Modify: `analysis/dashboard_assets/js/render.js` (append axis helpers)
- Modify: `analysis/dashboard_assets/css/dashboard.css` (append SVG ink rules)
- Modify: `analysis/build_dashboard.py` (`ASSET_ORDER`)
- Create: `tests/js/bars.test.mjs`

**Interfaces:**
- Consumes: `SOLAR.linear`, `ticks`, `roundedBarPath`, `fmt*`, `regionColorVar`, `el`, `svgEl`, `register`
- Produces on `SOLAR`:
  - `barSpec(rows, opts) -> {marks, ticks, width, height, plotLeft, plotRight, domainMax}` where `rows` is `[{key, label, value}]` and each mark is `{key, label, value, x, y, w, h, labelled}`
  - `stackSpec(rows, keys, opts) -> {marks, ticks, width, height, plotLeft, plotRight, domainMax}` where `rows` is `[{key, label, parts}]` and each mark is `{key, label, total, y, h, segments: [{key, x, w, value, labelled}]}`
  - `drawBars(spec, opts) -> SVGElement`, `drawStack(spec, keys, opts) -> SVGElement`
  - `drawAxisX(spec, format) -> SVGElement` (in `render.js`)
- Registers four ranked bar charts and one stacked chart.

Bar rules in force: thickness capped at 12px (well under the 24px ceiling), 4px rounded data-end with a square baseline, a 2px surface gap between the stacked segments, hairline solid gridlines. Values sit at the bar tip. With more than twelve bars, only the top three and the last are direct-labelled — a number on all 48 is the anti-pattern — and the table twin carries every value, which is also the relief the contrast WARN obliges.

- [ ] **Step 1: Write the failing test**

Create `tests/js/bars.test.mjs`:

```js
import test from "node:test";
import assert from "node:assert/strict";
import { load, payload } from "./load.mjs";

const S = load("boot.js", "core.js", "rollup.js", "filters.js", "render.js", "charts_bars.js");
const data = payload();

const OPTS = { width: 720, labelWidth: 150, valueWidth: 64, padTop: 8, padBottom: 32, thickness: 12, gap: 8 };

test("the longest bar reaches the plot's right edge", () => {
  const spec = S.barSpec([{ key: "a", label: "A", value: 10 }, { key: "b", label: "B", value: 5 }], OPTS);
  assert.equal(spec.plotLeft, 150);
  assert.equal(spec.plotRight, 656);
  assert.equal(spec.marks[0].w, 506);
  assert.equal(spec.marks[1].w, 253);
});

test("bar height accounts for the axis band, not just the bars", () => {
  const spec = S.barSpec([{ key: "a", label: "A", value: 1 }, { key: "b", label: "B", value: 1 }], OPTS);
  assert.equal(spec.height, 8 + 2 * 20 + 32);
});

test("bars stack downward at a constant band", () => {
  const rows = [1, 2, 3].map((n) => ({ key: String(n), label: String(n), value: n }));
  const spec = S.barSpec(rows, OPTS);
  assert.deepEqual(spec.marks.map((m) => m.y), [8, 28, 48]);
  assert.ok(spec.marks.every((m) => m.h === 12));
});

test("a zero value draws no bar and never a negative one", () => {
  const spec = S.barSpec([{ key: "a", label: "A", value: 0 }, { key: "b", label: "B", value: 4 }], OPTS);
  assert.equal(spec.marks[0].w, 0);
});

test("an empty row set produces an empty, valid spec", () => {
  const spec = S.barSpec([], OPTS);
  assert.deepEqual(spec.marks, []);
  assert.equal(spec.height, 40);
  assert.ok(spec.domainMax > 0, "domain must not be zero-width");
});

test("twelve or fewer bars are all labelled", () => {
  const rows = Array.from({ length: 12 }, (_, i) => ({ key: String(i), label: String(i), value: 12 - i }));
  assert.ok(S.barSpec(rows, OPTS).marks.every((m) => m.labelled));
});

test("past twelve bars only the extremes are labelled", () => {
  const rows = Array.from({ length: 48 }, (_, i) => ({ key: String(i), label: String(i), value: 48 - i }));
  const marks = S.barSpec(rows, OPTS).marks;
  assert.deepEqual(marks.map((m) => m.labelled).slice(0, 4), [true, true, true, false]);
  assert.equal(marks[47].labelled, true);
  assert.equal(marks.filter((m) => m.labelled).length, 4);
});

test("a named row is labelled even when it is not an extreme", () => {
  const rows = Array.from({ length: 48 }, (_, i) => ({ key: "c" + i, label: "c" + i, value: 48 - i }));
  const marks = S.barSpec(rows, Object.assign({ alwaysLabel: ["c20"] }, OPTS)).marks;
  assert.equal(marks[20].labelled, true);
});

test("ticks are clean and land inside the plot", () => {
  const spec = S.barSpec([{ key: "a", label: "A", value: 17.2 }], OPTS);
  assert.ok(spec.ticks.length >= 3);
  for (const tick of spec.ticks) {
    assert.ok(tick.x >= spec.plotLeft - 1e-9 && tick.x <= spec.plotRight + 1e-9);
  }
});

const STACK_OPTS = { width: 560, labelWidth: 120, valueWidth: 48, padTop: 8, padBottom: 32, thickness: 14, gap: 10, segGap: 2, minLabelWidth: 24 };
const BANDS = ["Low", "Medium", "High"];

test("stacked segments run left to right in band order", () => {
  const spec = S.stackSpec([{ key: "A", label: "A", parts: { Low: 1, Medium: 1, High: 2 } }], BANDS, STACK_OPTS);
  const segments = spec.marks[0].segments;
  assert.deepEqual(segments.map((s) => s.key), BANDS);
  assert.deepEqual(segments.map((s) => s.x), [120, 218, 316]);
});

test("a 2px surface gap separates every segment except the last", () => {
  const spec = S.stackSpec([{ key: "A", label: "A", parts: { Low: 1, Medium: 1, High: 2 } }], BANDS, STACK_OPTS);
  const segments = spec.marks[0].segments;
  assert.deepEqual(segments.map((s) => s.w), [96, 96, 196]);
});

test("the full stack ends exactly at the plot's right edge", () => {
  const spec = S.stackSpec([{ key: "A", label: "A", parts: { Low: 1, Medium: 1, High: 2 } }], BANDS, STACK_OPTS);
  const last = spec.marks[0].segments[2];
  assert.equal(last.x + last.w, spec.plotRight);
});

test("an empty band still gets a segment, with zero width and no label", () => {
  const spec = S.stackSpec([{ key: "A", label: "A", parts: { Low: 0, Medium: 2, High: 0 } }], BANDS, STACK_OPTS);
  const segments = spec.marks[0].segments;
  assert.equal(segments.length, 3);
  assert.equal(segments[0].w, 0);
  assert.equal(segments[0].labelled, false);
});

test("a segment too narrow for its number is not labelled inside", () => {
  const spec = S.stackSpec([{ key: "A", label: "A", parts: { Low: 1, Medium: 99, High: 0 } }], BANDS, STACK_OPTS);
  assert.equal(spec.marks[0].segments[0].labelled, false, "1 of 100 cannot hold a label");
  assert.equal(spec.marks[0].segments[1].labelled, true);
});

test("stack totals match the region risk counts from the payload", () => {
  const rows = data.regions.map((r) => ({
    key: r.region, label: r.region, parts: r.risk_counts,
  }));
  const spec = S.stackSpec(rows, BANDS, STACK_OPTS);
  assert.deepEqual(spec.marks.map((m) => m.total), data.regions.map((r) => r.cities));
  assert.equal(spec.marks.reduce((sum, m) => sum + m.total, 0), 48);
});

test("every bar chart in the registry declares a definition", () => {
  assert.ok(S.charts.length >= 5);
  for (const chart of S.charts) {
    assert.ok(chart.definition && chart.definition.length > 10, chart.id);
    assert.ok(chart.title, chart.id);
    assert.ok(["financial", "production", "sustainability"].includes(chart.page), chart.id);
  }
});

test("the registered charts include the five bar charts by id", () => {
  const ids = S.charts.map((c) => c.id);
  for (const id of ["roi-by-city", "risk-by-region", "production-by-country", "installations-by-region", "co2-by-country"]) {
    assert.ok(ids.includes(id), "missing " + id);
  }
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/js/bars.test.mjs`
Expected: FAIL — `ENOENT` on `charts_bars.js`

- [ ] **Step 3: Append the axis helper to `render.js`**

Add to `analysis/dashboard_assets/js/render.js`, inside the same IIFE, before the closing `})`:

```js
  S.drawAxisX = function (spec, format) {
    const group = S.svgEl("g", { class: "axis" });
    const baseline = spec.height - spec.padBottom + 0.5;
    for (const tick of spec.ticks) {
      group.appendChild(S.svgEl("g", { class: "tick" }, [
        S.svgEl("line", {
          x1: tick.x, x2: tick.x, y1: spec.padTop, y2: baseline, class: "gridline",
        }),
        S.svgEl("text", {
          x: tick.x, y: baseline + 16, "text-anchor": "middle", text: format(tick.value),
        }),
      ]));
    }
    group.appendChild(S.svgEl("line", {
      class: "axis-line",
      x1: spec.plotLeft, x2: spec.plotRight, y1: baseline, y2: baseline,
    }));
    return group;
  };

  S.svgRoot = function (spec, label) {
    return S.svgEl("svg", {
      viewBox: "0 0 " + spec.width + " " + spec.height,
      width: spec.width,
      height: spec.height,
      role: "img",
      "aria-label": label,
    });
  };
```

- [ ] **Step 4: Append the SVG ink rules to the stylesheet**

Add to the end of `analysis/dashboard_assets/css/dashboard.css`:

```css
.plot text { font-size: 11px; font-variant-numeric: tabular-nums; }
.plot .axis text { fill: var(--text-muted); }
.plot .gridline { stroke: var(--grid); stroke-width: 1; }
.plot .axis-line { stroke: var(--axis); stroke-width: 1; }
.plot .cat-label { fill: var(--text-secondary); }
.plot .value-label { fill: var(--text-primary); font-weight: 600; }
.plot .seg-label { font-size: 10px; font-weight: 600; }
.plot .hit { fill: transparent; cursor: pointer; }
.plot .mark { transition: opacity 120ms ease; }
.plot .mark.dim { opacity: 0.35; }
.plot .mark:hover { opacity: 0.85; }
.plot .note { fill: var(--text-muted); font-style: italic; }
```

- [ ] **Step 5: Write the bars module**

Create `analysis/dashboard_assets/js/charts_bars.js`:

```js
/* charts_bars.js — ranked horizontal bars and the stacked risk chart.
   Geometry is pure (barSpec, stackSpec); drawing is a thin pass over it. */
(function (S) {
  "use strict";

  const BAR_DEFAULTS = {
    width: 720, labelWidth: 150, valueWidth: 64,
    padTop: 8, padBottom: 32, thickness: 12, gap: 8,
    tickCount: 5, labelTop: 3, labelBottom: 1, alwaysLabel: [],
  };

  const STACK_DEFAULTS = {
    width: 560, labelWidth: 120, valueWidth: 48,
    padTop: 8, padBottom: 32, thickness: 14, gap: 10,
    segGap: 2, minLabelWidth: 24, tickCount: 4,
  };

  S.barSpec = function (rows, options) {
    const o = Object.assign({}, BAR_DEFAULTS, options || {});
    const plotLeft = o.labelWidth;
    const plotRight = o.width - o.valueWidth;
    const domainMax = rows.length ? Math.max.apply(null, rows.map((r) => r.value)) : 0;
    const domain = domainMax > 0 ? domainMax : 1;
    const x = S.linear(0, domain, plotLeft, plotRight);
    const band = o.thickness + o.gap;
    const dense = rows.length > 12;

    const marks = rows.map(function (row, i) {
      const named = o.alwaysLabel.indexOf(row.key) >= 0;
      const extreme = i < o.labelTop || i >= rows.length - o.labelBottom;
      return {
        key: row.key,
        label: row.label,
        value: row.value,
        meta: row.meta || null,
        x: plotLeft,
        y: o.padTop + i * band,
        w: Math.max(0, x(row.value) - plotLeft),
        h: o.thickness,
        labelled: !dense || extreme || named,
      };
    });

    return {
      marks: marks,
      ticks: S.ticks(0, domain, o.tickCount).map((v) => ({ value: v, x: x(v) })),
      width: o.width,
      height: o.padTop + rows.length * band + o.padBottom,
      padTop: o.padTop,
      padBottom: o.padBottom,
      plotLeft: plotLeft,
      plotRight: plotRight,
      domainMax: domain,
    };
  };

  S.stackSpec = function (rows, keys, options) {
    const o = Object.assign({}, STACK_DEFAULTS, options || {});
    const plotLeft = o.labelWidth;
    const plotRight = o.width - o.valueWidth;
    const span = plotRight - plotLeft;
    const totals = rows.map((r) => keys.reduce((sum, k) => sum + (r.parts[k] || 0), 0));
    const domainMax = totals.length ? Math.max.apply(null, totals) : 0;
    const domain = domainMax > 0 ? domainMax : 1;
    const band = o.thickness + o.gap;

    const marks = rows.map(function (row, i) {
      const total = totals[i];
      let lastFilled = -1;
      keys.forEach((k, j) => { if ((row.parts[k] || 0) > 0) lastFilled = j; });

      let cursor = plotLeft;
      const segments = keys.map(function (key, j) {
        const value = row.parts[key] || 0;
        const raw = (value / domain) * span;
        const width = value === 0 ? 0 : j === lastFilled ? raw : Math.max(0, raw - o.segGap);
        const segment = {
          key: key,
          value: value,
          x: cursor,
          w: width,
          labelled: raw >= o.minLabelWidth,
        };
        cursor += raw;
        return segment;
      });

      return {
        key: row.key,
        label: row.label,
        total: total,
        y: o.padTop + i * band,
        h: o.thickness,
        segments: segments,
      };
    });

    return {
      marks: marks,
      ticks: S.ticks(0, domain, o.tickCount).map((v) => ({ value: v, x: plotLeft + (v / domain) * span })),
      width: o.width,
      height: o.padTop + rows.length * band + o.padBottom,
      padTop: o.padTop,
      padBottom: o.padBottom,
      plotLeft: plotLeft,
      plotRight: plotRight,
      domainMax: domain,
    };
  };

  S.drawBars = function (spec, options) {
    const o = options || {};
    const svg = S.svgRoot(spec, o.ariaLabel || "Bar chart");
    svg.appendChild(S.drawAxisX(spec, o.tickFormat || S.fmtCompact));

    for (const mark of spec.marks) {
      const color = o.colorOf ? o.colorOf(mark) : "var(--series-1)";
      const group = S.svgEl("g", { class: "mark", "data-key": mark.key });

      group.appendChild(S.svgEl("text", {
        class: "cat-label",
        x: spec.plotLeft - 10,
        y: mark.y + mark.h - 1,
        "text-anchor": "end",
        text: mark.label,
      }));

      group.appendChild(S.svgEl("path", {
        d: S.roundedBarPath(mark.x, mark.y, mark.w, mark.h, 4),
        fill: color,
      }));

      if (mark.labelled) {
        group.appendChild(S.svgEl("text", {
          class: "value-label",
          x: mark.x + mark.w + 8,
          y: mark.y + mark.h - 1,
          text: (o.valueFormat || S.fmtCompact)(mark.value),
        }));
      }

      // Hit target spans the whole band, never just the painted pixels.
      const hit = S.svgEl("rect", {
        class: "hit",
        x: 0, y: mark.y - 4, width: spec.width, height: mark.h + 8,
        tabindex: "0",
        role: o.onSelect ? "button" : null,
        "aria-label": mark.label + ": " + (o.valueFormat || S.fmtCompact)(mark.value),
      });
      S.attachTip(hit, () => o.tip(mark));
      if (o.onSelect) {
        hit.addEventListener("click", () => o.onSelect(mark));
        hit.addEventListener("keydown", (event) => {
          if (event.key === "Enter" || event.key === " ") o.onSelect(mark);
        });
      }
      group.appendChild(hit);
      svg.appendChild(group);
    }
    return svg;
  };

  S.drawStack = function (spec, keys, options) {
    const o = options || {};
    const svg = S.svgRoot(spec, o.ariaLabel || "Stacked bar chart");
    svg.appendChild(S.drawAxisX(spec, o.tickFormat || S.fmtInt));

    for (const mark of spec.marks) {
      const group = S.svgEl("g", { class: "mark", "data-key": mark.key });
      group.appendChild(S.svgEl("text", {
        class: "cat-label",
        x: spec.plotLeft - 10,
        y: mark.y + mark.h - 2,
        "text-anchor": "end",
        text: mark.label,
      }));

      for (const segment of mark.segments) {
        if (segment.w <= 0) continue;
        group.appendChild(S.svgEl("rect", {
          x: segment.x, y: mark.y, width: segment.w, height: mark.h,
          fill: o.colorOf(segment.key), rx: 2,
        }));
        if (segment.labelled) {
          group.appendChild(S.svgEl("text", {
            class: "seg-label",
            x: segment.x + segment.w / 2,
            y: mark.y + mark.h - 3,
            "text-anchor": "middle",
            fill: o.inkOn(segment.key),
            text: S.fmtInt(segment.value),
          }));
        }
      }

      group.appendChild(S.svgEl("text", {
        class: "value-label",
        x: spec.plotRight + 8,
        y: mark.y + mark.h - 2,
        text: S.fmtInt(mark.total),
      }));

      const hit = S.svgEl("rect", {
        class: "hit",
        x: 0, y: mark.y - 4, width: spec.width, height: mark.h + 8,
        tabindex: "0",
        role: o.onSelect ? "button" : null,
        "aria-label": o.ariaFor(mark),
      });
      S.attachTip(hit, () => o.tip(mark));
      if (o.onSelect) {
        hit.addEventListener("click", () => o.onSelect(mark));
        hit.addEventListener("keydown", (event) => {
          if (event.key === "Enter" || event.key === " ") o.onSelect(mark);
        });
      }
      group.appendChild(hit);
      svg.appendChild(group);
    }
    return svg;
  };

  const RISK_COLOR = {
    Low: "var(--status-good)",
    Medium: "var(--status-warning)",
    High: "var(--status-critical)",
  };
  // Chosen per band so an in-segment number always clears contrast on its fill.
  const RISK_INK = { Low: "#ffffff", Medium: "#0b0b0b", High: "#ffffff" };

  S.register({
    id: "roi-by-city",
    page: "financial",
    title: "Return on investment, city by city",
    definition:
      "ROI_Percentage as supplied in the source data, one bar per city, highest first. " +
      "Dubai is labelled because the reference dashboard omitted it entirely.",
    wide: true,
    render: function (container, ctx) {
      const rows = ctx.cities.map((c) => ({
        key: c.city, label: c.city + " · " + c.country, value: c.roi_pct, meta: c,
      }));
      const spec = S.barSpec(rows, { width: 720, labelWidth: 190, alwaysLabel: ["Dubai"] });
      container.appendChild(S.drawBars(spec, {
        ariaLabel: "Return on investment by city, highest first",
        valueFormat: (v) => S.fmt1(v) + "%",
        tickFormat: (v) => S.fmt1(v) + "%",
        colorOf: (mark) => S.regionColorVar(mark.meta.region, ctx.allRegions),
        onSelect: (mark) => ctx.isolate("regions", mark.meta.region),
        tip: (mark) => ({
          value: S.fmt1(mark.value) + "% ROI",
          label: mark.meta.city + ", " + mark.meta.country,
          rows: [
            ["Region", mark.meta.region],
            ["Payback", S.fmt1(mark.meta.payback_years) + " years (" + mark.meta.risk_band + ")"],
            ["Production", S.fmtInt(mark.meta.production_kwh) + " kWh/yr"],
            ["Installations", S.fmtInt(mark.meta.installations)],
          ],
        }),
      }));
    },
    table: (ctx) => ({
      caption: "Return on investment by city",
      columns: ["City", "Country", "Region", "ROI %", "Payback (yrs)", "Risk"],
      rows: ctx.cities.map((c) => [
        c.city, c.country, c.region, S.fmt1(c.roi_pct), S.fmt1(c.payback_years), c.risk_band,
      ]),
    }),
  });

  S.register({
    id: "risk-by-region",
    page: "financial",
    title: "Payback risk by region",
    definition:
      "Payback risk: Low under 7 years, Medium 7 to 9 inclusive, High above 9. " +
      "Counts are cities, not weighted by installed capacity.",
    render: function (container, ctx) {
      const rows = ctx.regions.map((r) => ({
        key: r.region, label: r.region, parts: r.risk_counts, meta: r,
      }));
      const spec = S.stackSpec(rows, S.BANDS, {});
      container.appendChild(S.el("ul", { class: "legend" }, S.BANDS.map((band) =>
        S.el("li", null, [
          S.el("span", { class: "swatch", style: "background:" + RISK_COLOR[band] }),
          S.el("span", { text: band }),
        ])
      )));
      container.appendChild(S.drawStack(spec, S.BANDS, {
        ariaLabel: "Cities per payback risk band, by region",
        colorOf: (band) => RISK_COLOR[band],
        inkOn: (band) => RISK_INK[band],
        ariaFor: (mark) => mark.label + ": " + S.BANDS
          .map((b) => S.fmtInt(mark.segments.find((s) => s.key === b).value) + " " + b)
          .join(", "),
        onSelect: (mark) => ctx.isolate("regions", mark.key),
        tip: (mark) => ({
          value: S.fmtInt(mark.total) + " cities",
          label: mark.label,
          rows: mark.segments.map((s) => [s.key + " risk", S.fmtInt(s.value)]),
        }),
      }));
    },
    table: (ctx) => ({
      caption: "Cities per payback risk band",
      columns: ["Region", "Low", "Medium", "High", "Cities"],
      rows: ctx.regions.map((r) => [
        r.region, S.fmtInt(r.risk_counts.Low), S.fmtInt(r.risk_counts.Medium),
        S.fmtInt(r.risk_counts.High), S.fmtInt(r.cities),
      ]),
    }),
  });

  S.register({
    id: "production-by-country",
    page: "production",
    title: "Average annual production by country",
    definition:
      "Mean Avg_Annual_Production_kWh across the cities sampled in each country. " +
      "A country's mean says nothing about how many systems it has installed.",
    wide: true,
    render: function (container, ctx) {
      const rows = ctx.countries
        .slice()
        .sort((a, b) => b.mean_production_kwh - a.mean_production_kwh || a.country.localeCompare(b.country))
        .map((c) => ({ key: c.country, label: c.country, value: c.mean_production_kwh, meta: c }));
      container.appendChild(S.drawBars(S.barSpec(rows, { width: 720, labelWidth: 160 }), {
        ariaLabel: "Mean annual production by country",
        valueFormat: S.fmtInt,
        colorOf: (mark) => S.regionColorVar(mark.meta.region, ctx.allRegions),
        onSelect: (mark) => ctx.isolate("regions", mark.meta.region),
        tip: (mark) => ({
          value: S.fmtInt(mark.value) + " kWh/yr",
          label: mark.label,
          rows: [["Region", mark.meta.region], ["Cities sampled", S.fmtInt(mark.meta.cities)]],
        }),
      }));
    },
    table: (ctx) => ({
      caption: "Mean annual production by country",
      columns: ["Country", "Region", "Cities", "Mean kWh/yr"],
      rows: ctx.countries.map((c) => [
        c.country, c.region, S.fmtInt(c.cities), S.fmtInt(c.mean_production_kwh),
      ]),
    }),
  });

  S.register({
    id: "installations-by-region",
    page: "production",
    title: "Installations by region",
    definition:
      "Sum of Solar_Installations_Count. Bars, not an area chart: there is no " +
      "continuity between Africa and Asia for an area to imply.",
    render: function (container, ctx) {
      const rows = ctx.regions
        .slice()
        .sort((a, b) => b.installations - a.installations)
        .map((r) => ({ key: r.region, label: r.region, value: r.installations, meta: r }));
      container.appendChild(S.drawBars(S.barSpec(rows, { width: 560, labelWidth: 120 }), {
        ariaLabel: "Total installations by region",
        valueFormat: S.fmtCompact,
        colorOf: (mark) => S.regionColorVar(mark.key, ctx.allRegions),
        onSelect: (mark) => ctx.isolate("regions", mark.key),
        tip: (mark) => ({
          value: S.fmtInt(mark.value) + " installations",
          label: mark.label,
          rows: [["Cities", S.fmtInt(mark.meta.cities)], ["Mean ROI", S.fmt2(mark.meta.mean_roi) + "%"]],
        }),
      }));
    },
    table: (ctx) => ({
      caption: "Installations by region",
      columns: ["Region", "Cities", "Installations"],
      rows: ctx.regions.map((r) => [r.region, S.fmtInt(r.cities), S.fmtInt(r.installations)]),
    }),
  });

  S.register({
    id: "co2-by-country",
    page: "sustainability",
    title: "CO₂ avoided per year by country",
    definition:
      "Sum of CO2_Reduction_Tons_per_Year. This is a fixed multiple of annual " +
      "production, so it ranks countries by output, not by carbon intensity.",
    wide: true,
    render: function (container, ctx) {
      const rows = ctx.countries.map((c) => ({
        key: c.country, label: c.country, value: c.co2_tons, meta: c,
      }));
      container.appendChild(S.drawBars(S.barSpec(rows, { width: 720, labelWidth: 160 }), {
        ariaLabel: "Tonnes of CO2 avoided per year by country",
        valueFormat: (v) => S.fmt2(v) + " t",
        tickFormat: (v) => S.fmt1(v),
        colorOf: (mark) => S.regionColorVar(mark.meta.region, ctx.allRegions),
        onSelect: (mark) => ctx.isolate("regions", mark.meta.region),
        tip: (mark) => ({
          value: S.fmt2(mark.value) + " t CO₂/yr",
          label: mark.label,
          rows: [["Region", mark.meta.region], ["Cities", S.fmtInt(mark.meta.cities)]],
        }),
      }));
    },
    table: (ctx) => ({
      caption: "CO₂ avoided per year by country",
      columns: ["Country", "Region", "Cities", "Tonnes CO₂/yr"],
      rows: ctx.countries.map((c) => [
        c.country, c.region, S.fmtInt(c.cities), S.fmt2(c.co2_tons),
      ]),
    }),
  });
})(globalThis.SOLAR);
```

- [ ] **Step 6: Add the tooltip attachment point**

`drawBars` calls `S.attachTip`. Add it to `analysis/dashboard_assets/js/render.js`, inside the same IIFE. The full tooltip element is built in Task 9; this is the hook plus a working default.

```js
  S.tipModel = null;  // last model requested, exposed for tests

  S.attachTip = function (node, modelFn) {
    node.addEventListener("pointerenter", () => { S.tipModel = modelFn(); S.showTip(S.tipModel); });
    node.addEventListener("focus", () => { S.tipModel = modelFn(); S.showTip(S.tipModel); });
    node.addEventListener("pointerleave", () => S.hideTip());
    node.addEventListener("blur", () => S.hideTip());
    node.addEventListener("pointermove", (event) => S.moveTip(event));
  };

  S.showTip = function () {};   // replaced in Task 9
  S.hideTip = function () {};
  S.moveTip = function () {};
```

- [ ] **Step 7: Run test to verify it passes**

Run: `node --test tests/js/bars.test.mjs`
Expected: 17 pass, 0 fail

- [ ] **Step 8: Register the asset and rebuild**

In `analysis/build_dashboard.py`, insert `"js/charts_bars.js"` into `ASSET_ORDER` **before** `"js/app.js"`.

Run: `python -m pytest tests/ -q` — all pass
Run: `node --test "tests/js/*.test.mjs"` — all pass
Run: `python -m analysis.build_dashboard`

Open `output/dashboard.html`. Expected: page 1 shows the 48-bar ROI chart with Dubai labelled at rank 2 and the stacked risk chart summing 5 / 19 / 24; page 2 shows production by country and installations by region; page 3 shows CO₂ by country. Clicking any bar isolates that region and every chart and KPI re-renders. Ticking "Show values as tables" reveals a table under each.

Check by eye before continuing: no label overflows its bar, no axis label is clipped by the card, and the bars do not touch each other.

- [ ] **Step 9: Commit**

```bash
git add analysis/dashboard_assets analysis/build_dashboard.py tests/js/bars.test.mjs
git -c user.name="chinm" -c user.email="mishraswagat2804@gmail.com" commit -m "feat: add ranked bar charts and the stacked payback-risk chart"
```

---

### Task 6: Dot plots — regional ROI rank and production consistency

**Files:**
- Create: `analysis/dashboard_assets/js/charts_dots.js`
- Modify: `analysis/build_dashboard.py` (`ASSET_ORDER`)
- Create: `tests/js/dots.test.mjs`

**Interfaces:**
- Consumes: `SOLAR.linear`, `ticks`, `svgRoot`, `drawAxisX`, `attachTip`, `regionColorVar`, `register`
- Produces on `SOLAR`:
  - `dotSpec(rows, opts) -> {marks, ticks, width, height, plotLeft, plotRight, domainMin, domainMax}` where `rows` is `[{key, label, value, note}]` with `value === null` meaning not computable, and each mark is `{key, label, value, note, cx, cy, r, missing}`
  - `drawDots(spec, opts) -> SVGElement`
- Registers `regional-roi-rank` (financial) and `production-consistency` (production).

The n/a rule is the whole point of the consistency chart: Middle East has one city, so its consistency is `null`, and a `null` must render as the words "n/a — 1 city" on the row rather than as a dot at zero or a dot at one. Both readings would be lies. Small-sample regions (under 5 cities) keep their dot but carry an `n=3`-style note.

- [ ] **Step 1: Write the failing test**

Create `tests/js/dots.test.mjs`:

```js
import test from "node:test";
import assert from "node:assert/strict";
import { load, payload } from "./load.mjs";

const S = load("boot.js", "core.js", "rollup.js", "filters.js", "render.js", "charts_dots.js");
const data = payload();

const OPTS = { width: 520, labelWidth: 130, valueWidth: 70, padTop: 12, padBottom: 32, band: 26, radius: 5 };

test("dots sit on the value scale", () => {
  const spec = S.dotSpec(
    [{ key: "a", label: "A", value: 0 }, { key: "b", label: "B", value: 10 }],
    Object.assign({ domainMin: 0, domainMax: 10 }, OPTS)
  );
  assert.equal(spec.marks[0].cx, 130);
  assert.equal(spec.marks[1].cx, 450);
});

test("rows are spaced one band apart", () => {
  const rows = ["a", "b", "c"].map((k) => ({ key: k, label: k, value: 1 }));
  const spec = S.dotSpec(rows, Object.assign({ domainMin: 0, domainMax: 2 }, OPTS));
  assert.deepEqual(spec.marks.map((m) => m.cy), [12 + 13, 12 + 39, 12 + 65]);
});

test("markers are at least 8px across", () => {
  const spec = S.dotSpec([{ key: "a", label: "A", value: 1 }], Object.assign({ domainMin: 0, domainMax: 2 }, OPTS));
  assert.ok(spec.marks[0].r >= 4, "radius under 4 gives a marker under 8px");
});

test("a null value is marked missing and carries no coordinate", () => {
  const spec = S.dotSpec(
    [{ key: "a", label: "A", value: null, note: "1 city" }],
    Object.assign({ domainMin: 0, domainMax: 1 }, OPTS)
  );
  assert.equal(spec.marks[0].missing, true);
  assert.equal(spec.marks[0].cx, null);
  assert.equal(spec.marks[0].note, "1 city");
});

test("a domain is derived from the data when not supplied", () => {
  const spec = S.dotSpec(
    [{ key: "a", label: "A", value: 4 }, { key: "b", label: "B", value: 9 }],
    OPTS
  );
  assert.ok(spec.domainMin <= 4 && spec.domainMax >= 9);
});

test("missing values do not drag the domain to zero", () => {
  const spec = S.dotSpec(
    [{ key: "a", label: "A", value: null }, { key: "b", label: "B", value: 9 }],
    OPTS
  );
  assert.ok(spec.domainMin > 0, "a null must not be read as a zero");
});

test("all-missing rows still produce a valid spec", () => {
  const spec = S.dotSpec([{ key: "a", label: "A", value: null }], OPTS);
  assert.equal(spec.marks.length, 1);
  assert.ok(spec.domainMax > spec.domainMin);
});

test("regional consistency reproduces the payload, nulls included", () => {
  const rows = data.regions.map((r) => ({
    key: r.region, label: r.region, value: r.consistency,
  }));
  const spec = S.dotSpec(rows, OPTS);
  const middleEast = spec.marks.find((m) => m.key === "Middle East");
  assert.equal(middleEast.missing, true, "Middle East has one city; consistency is not computable");
  const europe = spec.marks.find((m) => m.key === "Europe");
  assert.equal(europe.missing, false);
});

test("both dot charts are registered with definitions", () => {
  const ids = S.charts.map((c) => c.id);
  assert.ok(ids.includes("regional-roi-rank"));
  assert.ok(ids.includes("production-consistency"));
  for (const chart of S.charts) {
    assert.ok(chart.definition.length > 10, chart.id);
  }
});

test("the consistency table spells out n/a rather than leaving a blank", () => {
  const chart = S.charts.find((c) => c.id === "production-consistency");
  const model = chart.table({ regions: data.regions });
  const middleEast = model.rows.find((row) => row[0] === "Middle East");
  assert.equal(middleEast[2], "n/a");
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/js/dots.test.mjs`
Expected: FAIL — `ENOENT` on `charts_dots.js`

- [ ] **Step 3: Write the implementation**

Create `analysis/dashboard_assets/js/charts_dots.js`:

```js
/* charts_dots.js — ordered dot plots.
   A null value is not a zero and not a one: it is rendered as words. */
(function (S) {
  "use strict";

  const DOT_DEFAULTS = {
    width: 520, labelWidth: 130, valueWidth: 70,
    padTop: 12, padBottom: 32, band: 26, radius: 5, tickCount: 4,
  };

  S.dotSpec = function (rows, options) {
    const o = Object.assign({}, DOT_DEFAULTS, options || {});
    const plotLeft = o.labelWidth;
    const plotRight = o.width - o.valueWidth;
    const present = rows.filter((r) => r.value !== null && r.value !== undefined);

    let domainMin = o.domainMin;
    let domainMax = o.domainMax;
    if (domainMin === undefined || domainMax === undefined) {
      const values = present.map((r) => r.value);
      const lo = values.length ? Math.min.apply(null, values) : 0;
      const hi = values.length ? Math.max.apply(null, values) : 1;
      const pad = (hi - lo) * 0.15 || Math.max(Math.abs(hi) * 0.1, 1);
      if (domainMin === undefined) domainMin = lo - pad;
      if (domainMax === undefined) domainMax = hi + pad;
    }
    if (!(domainMax > domainMin)) domainMax = domainMin + 1;

    const x = S.linear(domainMin, domainMax, plotLeft, plotRight);
    const marks = rows.map(function (row, i) {
      const missing = row.value === null || row.value === undefined;
      return {
        key: row.key,
        label: row.label,
        value: row.value,
        note: row.note || null,
        meta: row.meta || null,
        missing: missing,
        cx: missing ? null : x(row.value),
        cy: o.padTop + i * o.band + o.band / 2,
        r: o.radius,
      };
    });

    return {
      marks: marks,
      ticks: S.ticks(domainMin, domainMax, o.tickCount).map((v) => ({ value: v, x: x(v) })),
      width: o.width,
      height: o.padTop + rows.length * o.band + o.padBottom,
      padTop: o.padTop,
      padBottom: o.padBottom,
      plotLeft: plotLeft,
      plotRight: plotRight,
      domainMin: domainMin,
      domainMax: domainMax,
    };
  };

  S.drawDots = function (spec, options) {
    const o = options || {};
    const svg = S.svgRoot(spec, o.ariaLabel || "Dot plot");
    svg.appendChild(S.drawAxisX(spec, o.tickFormat || S.fmt1));

    for (const mark of spec.marks) {
      const group = S.svgEl("g", { class: "mark", "data-key": mark.key });
      group.appendChild(S.svgEl("text", {
        class: "cat-label",
        x: spec.plotLeft - 10, y: mark.cy + 4, "text-anchor": "end", text: mark.label,
      }));

      if (mark.missing) {
        group.appendChild(S.svgEl("text", {
          class: "note",
          x: spec.plotLeft + 4, y: mark.cy + 4,
          text: "n/a — " + (mark.note || "not computable"),
        }));
      } else {
        // 2px surface ring keeps overlapping dots legible.
        group.appendChild(S.svgEl("circle", {
          cx: mark.cx, cy: mark.cy, r: mark.r + 2, fill: "var(--surface-1)",
        }));
        group.appendChild(S.svgEl("circle", {
          cx: mark.cx, cy: mark.cy, r: mark.r,
          fill: o.colorOf ? o.colorOf(mark) : "var(--series-1)",
        }));
        group.appendChild(S.svgEl("text", {
          class: "value-label",
          x: spec.plotRight + 10, y: mark.cy + 4,
          text: (o.valueFormat || S.fmt2)(mark.value) + (mark.note ? " · " + mark.note : ""),
        }));
      }

      const hit = S.svgEl("rect", {
        class: "hit",
        x: 0, y: mark.cy - 13, width: spec.width, height: 26,
        tabindex: "0",
        role: o.onSelect ? "button" : null,
        "aria-label": o.ariaFor(mark),
      });
      S.attachTip(hit, () => o.tip(mark));
      if (o.onSelect) {
        hit.addEventListener("click", () => o.onSelect(mark));
        hit.addEventListener("keydown", (event) => {
          if (event.key === "Enter" || event.key === " ") o.onSelect(mark);
        });
      }
      group.appendChild(hit);
      svg.appendChild(group);
    }
    return svg;
  };

  S.register({
    id: "regional-roi-rank",
    page: "financial",
    title: "Regional ROI ranking",
    definition:
      "Dense rank on mean ROI_Percentage, highest first — tied regions share a " +
      "rank and the next is not skipped. Regions under five cities are marked.",
    render: function (container, ctx) {
      const rows = ctx.regions.map((r) => ({
        key: r.region,
        label: "#" + r.rank + "  " + r.region,
        value: r.mean_roi,
        note: r.small_sample ? "n=" + r.cities : null,
        meta: r,
      }));
      container.appendChild(S.drawDots(S.dotSpec(rows, { width: 540, labelWidth: 150 }), {
        ariaLabel: "Mean return on investment by region, best rank first",
        valueFormat: (v) => S.fmt2(v) + "%",
        tickFormat: (v) => S.fmt1(v) + "%",
        colorOf: (mark) => S.regionColorVar(mark.key, ctx.allRegions),
        ariaFor: (mark) => mark.label + ": " + S.fmt2(mark.value) + "% mean ROI",
        onSelect: (mark) => ctx.isolate("regions", mark.key),
        tip: (mark) => ({
          value: S.fmt2(mark.value) + "% mean ROI",
          label: mark.meta.region + " · rank " + mark.meta.rank,
          rows: [
            ["Cities", S.fmtInt(mark.meta.cities)],
            ["Installations", S.fmtInt(mark.meta.installations)],
          ],
        }),
      }));
    },
    table: (ctx) => ({
      caption: "Mean ROI by region",
      columns: ["Region", "Rank", "Mean ROI %", "Cities"],
      rows: ctx.regions.map((r) => [
        r.region, String(r.rank), S.fmt2(r.mean_roi), S.fmtInt(r.cities),
      ]),
    }),
  });

  S.register({
    id: "production-consistency",
    page: "production",
    title: "Production consistency by region",
    definition:
      "1 − (σ ÷ μ) of Avg_Annual_Production_kWh within a region, sample σ, clamped " +
      "to 0–1. Not computable under three cities: one city has no spread, which " +
      "would otherwise read as perfect consistency.",
    render: function (container, ctx) {
      const rows = ctx.regions
        .slice()
        .sort((a, b) => (b.consistency === null ? -1 : b.consistency) - (a.consistency === null ? -1 : a.consistency))
        .map((r) => ({
          key: r.region,
          label: r.region,
          value: r.consistency,
          note: r.consistency === null ? r.cities + (r.cities === 1 ? " city" : " cities") : (r.small_sample ? "n=" + r.cities : null),
          meta: r,
        }));
      container.appendChild(S.drawDots(S.dotSpec(rows, { width: 540, labelWidth: 130, domainMin: 0, domainMax: 1 }), {
        ariaLabel: "Production consistency by region",
        valueFormat: S.fmt2,
        tickFormat: S.fmt2,
        colorOf: (mark) => S.regionColorVar(mark.key, ctx.allRegions),
        ariaFor: (mark) => mark.missing
          ? mark.label + ": not computable, " + mark.note
          : mark.label + ": consistency " + S.fmt2(mark.value),
        onSelect: (mark) => ctx.isolate("regions", mark.key),
        tip: (mark) => ({
          value: mark.missing ? "n/a" : S.fmt2(mark.value),
          label: mark.label + (mark.missing ? " — needs 3+ cities" : " production consistency"),
          rows: [
            ["Cities", S.fmtInt(mark.meta.cities)],
            ["Production", S.fmtInt(mark.meta.production_kwh) + " kWh/yr"],
          ],
        }),
      }));
    },
    table: (ctx) => ({
      caption: "Production consistency by region",
      columns: ["Region", "Cities", "Consistency"],
      rows: ctx.regions.map((r) => [
        r.region, S.fmtInt(r.cities), r.consistency === null ? "n/a" : S.fmt2(r.consistency),
      ]),
    }),
  });
})(globalThis.SOLAR);
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test tests/js/dots.test.mjs`
Expected: 10 pass, 0 fail

- [ ] **Step 5: Register the asset, rebuild, and look at it**

Insert `"js/charts_dots.js"` into `ASSET_ORDER` before `"js/app.js"`.

Run: `python -m pytest tests/ -q` and `node --test "tests/js/*.test.mjs"` — all pass
Run: `python -m analysis.build_dashboard`

Open the page. Expected: page 1 gains the ranked ROI dot plot with Middle East at #1 carrying `n=1`; page 2 gains the consistency plot where Middle East reads `n/a — 1 city` rather than a dot. Filter to Oceania and confirm the consistency chart still computes (3 cities) while a filter down to 2 cities flips it to n/a.

- [ ] **Step 6: Commit**

```bash
git add analysis/dashboard_assets analysis/build_dashboard.py tests/js/dots.test.mjs
git -c user.name="chinm" -c user.email="mishraswagat2804@gmail.com" commit -m "feat: add regional ROI rank and production consistency dot plots"
```

---

### Task 7: Scatter — two clouds and one faceted small-multiple

**Files:**
- Create: `analysis/dashboard_assets/js/charts_scatter.js`
- Modify: `analysis/dashboard_assets/js/render.js` (append `drawAxisY`)
- Modify: `analysis/build_dashboard.py` (`ASSET_ORDER`)
- Create: `tests/js/scatter.test.mjs`

**Interfaces:**
- Consumes: `SOLAR.linear`, `extent`, `ticks`, `svgRoot`, `attachTip`, `regionColorVar`, `register`
- Produces on `SOLAR`:
  - `scatterSpec(points, opts) -> {marks, xTicks, yTicks, width, height, plotLeft, plotRight, plotTop, plotBottom, xDomain, yDomain}` where `points` is `[{key, label, x, y, meta}]`
  - `nearestMark(spec, px, py) -> mark | null`
  - `facetSpecs(points, opts) -> [{key, spec, marks, contextMarks, col, row, x, y}]`
  - `drawScatter(spec, opts) -> SVGElement`
  - `drawFacets(facets, opts) -> SVGElement`
  - `drawAxisY(spec, format) -> SVGElement` (in `render.js`)
- Registers `installations-vs-roi` (financial), `ghi-vs-production` (production), `roi-vs-viability` (sustainability).

**Why the GHI chart is faceted rather than colour-coded.** The spec asks for production against GHI "colored by region". Seven region hues in one scatter is an all-pairs colour problem, and the validated palette clears the all-pairs floors for three slots only — past that, no ordering of these hues can, so the dataviz rule is to facet instead of to cycle. Seven small panels sharing one pair of axes give each region its own hue against a muted context cloud of all 48 cities, which reads the regional pattern *better* than an overplotted single panel would. Record this in `docs/DECISIONS.md` in Task 10.

Each cloud carries its correlation as a written callout — the numbers come from `payload.correlations`, computed by Python, never recomputed here.

- [ ] **Step 1: Write the failing test**

Create `tests/js/scatter.test.mjs`:

```js
import test from "node:test";
import assert from "node:assert/strict";
import { load, payload } from "./load.mjs";

const S = load("boot.js", "core.js", "rollup.js", "filters.js", "render.js", "charts_scatter.js");
const data = payload();

const OPTS = {
  width: 520, height: 320, padTop: 20, padRight: 20, padBottom: 40, padLeft: 60,
  radius: 5, xDomain: [0, 10], yDomain: [0, 10],
};

const pt = (key, x, y) => ({ key: key, label: key, x: x, y: y, meta: { key: key } });

test("x grows rightward and y grows upward", () => {
  const spec = S.scatterSpec([pt("a", 0, 0), pt("b", 10, 10)], OPTS);
  assert.equal(spec.marks[0].cx, 60);
  assert.equal(spec.marks[0].cy, 280);
  assert.equal(spec.marks[1].cx, 500);
  assert.equal(spec.marks[1].cy, 20);
});

test("the plot box excludes the axis bands", () => {
  const spec = S.scatterSpec([pt("a", 5, 5)], OPTS);
  assert.equal(spec.plotLeft, 60);
  assert.equal(spec.plotRight, 500);
  assert.equal(spec.plotTop, 20);
  assert.equal(spec.plotBottom, 280);
});

test("markers are at least 8px across", () => {
  const spec = S.scatterSpec([pt("a", 5, 5)], OPTS);
  assert.ok(spec.marks[0].r >= 4);
});

test("a derived domain pads the extent so points never sit on the frame", () => {
  const spec = S.scatterSpec([pt("a", 2, 2), pt("b", 8, 8)], { width: 520, height: 320 });
  assert.ok(spec.xDomain[0] < 2 && spec.xDomain[1] > 8);
  assert.ok(spec.yDomain[0] < 2 && spec.yDomain[1] > 8);
});

test("identical values still yield a usable domain", () => {
  const spec = S.scatterSpec([pt("a", 5, 5), pt("b", 5, 5)], { width: 520, height: 320 });
  assert.ok(spec.xDomain[1] > spec.xDomain[0]);
  assert.ok(spec.yDomain[1] > spec.yDomain[0]);
});

test("an empty cloud produces a valid empty spec", () => {
  const spec = S.scatterSpec([], { width: 520, height: 320 });
  assert.deepEqual(spec.marks, []);
  assert.ok(spec.xTicks.length >= 1);
});

test("nearest point wins even when the pointer is nowhere near it", () => {
  const spec = S.scatterSpec([pt("a", 0, 0), pt("b", 10, 10)], OPTS);
  assert.equal(S.nearestMark(spec, 70, 270).key, "a");
  assert.equal(S.nearestMark(spec, 480, 40).key, "b");
});

test("nearest point on an empty cloud is null, not a crash", () => {
  assert.equal(S.nearestMark(S.scatterSpec([], OPTS), 10, 10), null);
});

test("facets share one pair of domains across every panel", () => {
  const points = [pt("a", 1, 1), pt("b", 9, 9), pt("c", 5, 5)];
  points[0].facet = "X";
  points[1].facet = "Y";
  points[2].facet = "X";
  const facets = S.facetSpecs(points, {
    facetOf: (p) => p.facet, width: 520, columns: 2, panelHeight: 140,
  });
  assert.equal(facets.length, 2);
  assert.deepEqual(facets[0].spec.xDomain, facets[1].spec.xDomain);
  assert.deepEqual(facets[0].spec.yDomain, facets[1].spec.yDomain);
});

test("each facet holds its own points and the full context cloud", () => {
  const points = [pt("a", 1, 1), pt("b", 9, 9), pt("c", 5, 5)];
  points[0].facet = "X";
  points[1].facet = "Y";
  points[2].facet = "X";
  const facets = S.facetSpecs(points, {
    facetOf: (p) => p.facet, width: 520, columns: 2, panelHeight: 140,
  });
  const x = facets.find((f) => f.key === "X");
  assert.equal(x.marks.length, 2);
  assert.equal(x.contextMarks.length, 3);
});

test("facets lay out in a grid, left to right then down", () => {
  const points = ["A", "B", "C"].map((k, i) => Object.assign(pt(k, i, i), { facet: k }));
  const facets = S.facetSpecs(points, {
    facetOf: (p) => p.facet, width: 600, columns: 2, panelHeight: 140, gap: 20,
  });
  assert.deepEqual(facets.map((f) => [f.col, f.row]), [[0, 0], [1, 0], [0, 1]]);
  assert.equal(facets[0].x, 0);
  assert.equal(facets[1].x, 310);
  assert.equal(facets[2].y, facets[0].y + 140 + 20);
});

test("the seven regions facet into seven panels", () => {
  const points = data.cities.map((c) => ({
    key: c.city, label: c.city, x: c.ghi, y: c.production_kwh, meta: c,
  }));
  const facets = S.facetSpecs(points, {
    facetOf: (p) => p.meta.region, width: 720, columns: 4, panelHeight: 150,
  });
  assert.equal(facets.length, 7);
  assert.equal(facets.reduce((sum, f) => sum + f.marks.length, 0), 48);
});

test("the three scatter charts are registered", () => {
  const ids = S.charts.map((c) => c.id);
  for (const id of ["installations-vs-roi", "ghi-vs-production", "roi-vs-viability"]) {
    assert.ok(ids.includes(id), "missing " + id);
  }
});

test("the correlation callouts quote the payload, never a recomputed number", () => {
  const ctx = { payload: data, cities: data.cities };
  const chart = S.charts.find((c) => c.id === "installations-vs-roi");
  assert.match(chart.callout(ctx), /0\.137/);
  const viability = S.charts.find((c) => c.id === "roi-vs-viability");
  assert.match(viability.callout(ctx), /0\.982/);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/js/scatter.test.mjs`
Expected: FAIL — `ENOENT` on `charts_scatter.js`

- [ ] **Step 3: Append the y-axis helper to `render.js`**

Add inside the `render.js` IIFE:

```js
  S.drawAxisY = function (spec, format) {
    const group = S.svgEl("g", { class: "axis" });
    for (const tick of spec.yTicks) {
      group.appendChild(S.svgEl("g", { class: "tick" }, [
        S.svgEl("line", {
          class: "gridline",
          x1: spec.plotLeft, x2: spec.plotRight, y1: tick.y, y2: tick.y,
        }),
        S.svgEl("text", {
          x: spec.plotLeft - 10, y: tick.y + 4, "text-anchor": "end", text: format(tick.value),
        }),
      ]));
    }
    return group;
  };

  S.axisTitle = function (text, x, y, anchor, rotate) {
    return S.svgEl("text", {
      class: "axis-title",
      x: x, y: y, "text-anchor": anchor || "middle",
      transform: rotate ? "rotate(-90 " + x + " " + y + ")" : null,
      text: text,
    });
  };
```

And append to `dashboard.css`:

```css
.plot .axis-title { fill: var(--text-muted); font-size: 11px; letter-spacing: 0.04em; }
.plot .facet-title { fill: var(--text-secondary); font-size: 11px; font-weight: 600; }
.plot .context-dot { fill: var(--context); }
```

- [ ] **Step 4: Write the implementation**

Create `analysis/dashboard_assets/js/charts_scatter.js`:

```js
/* charts_scatter.js — clouds and small multiples.
   Region colour is deliberately absent from the single-panel clouds: seven hues
   in one all-pairs form is past what the validated palette supports, so the
   regional view is faceted instead. */
(function (S) {
  "use strict";

  const SCATTER_DEFAULTS = {
    width: 520, height: 320, padTop: 20, padRight: 20, padBottom: 40, padLeft: 60,
    radius: 5, xTickCount: 5, yTickCount: 4,
  };

  function padded(lo, hi) {
    const pad = (hi - lo) * 0.08 || Math.max(Math.abs(hi) * 0.1, 1);
    return [lo - pad, hi + pad];
  }

  S.scatterSpec = function (points, options) {
    const o = Object.assign({}, SCATTER_DEFAULTS, options || {});
    const plotLeft = o.padLeft;
    const plotRight = o.width - o.padRight;
    const plotTop = o.padTop;
    const plotBottom = o.height - o.padBottom;

    const xDomain = o.xDomain || padded.apply(null, S.extent(points, (p) => p.x));
    const yDomain = o.yDomain || padded.apply(null, S.extent(points, (p) => p.y));
    const x = S.linear(xDomain[0], xDomain[1], plotLeft, plotRight);
    const y = S.linear(yDomain[0], yDomain[1], plotBottom, plotTop);

    return {
      marks: points.map((p) => ({
        key: p.key, label: p.label, meta: p.meta,
        value: { x: p.x, y: p.y },
        cx: x(p.x), cy: y(p.y), r: o.radius,
      })),
      xTicks: S.ticks(xDomain[0], xDomain[1], o.xTickCount).map((v) => ({ value: v, x: x(v) })),
      yTicks: S.ticks(yDomain[0], yDomain[1], o.yTickCount).map((v) => ({ value: v, y: y(v) })),
      width: o.width, height: o.height,
      padTop: o.padTop, padBottom: o.padBottom,
      plotLeft: plotLeft, plotRight: plotRight, plotTop: plotTop, plotBottom: plotBottom,
      ticks: S.ticks(xDomain[0], xDomain[1], o.xTickCount).map((v) => ({ value: v, x: x(v) })),
      xDomain: xDomain, yDomain: yDomain,
    };
  };

  // Nearest-point lookup: the pointer only has to be closest, never dead-centre.
  S.nearestMark = function (spec, px, py) {
    let best = null;
    let bestDistance = Infinity;
    for (const mark of spec.marks) {
      const dx = mark.cx - px;
      const dy = mark.cy - py;
      const distance = dx * dx + dy * dy;
      if (distance < bestDistance) { bestDistance = distance; best = mark; }
    }
    return best;
  };

  S.facetSpecs = function (points, options) {
    const o = Object.assign({ columns: 4, gap: 20, panelHeight: 150, width: 720 }, options);
    const groups = S.groupBy(points, o.facetOf);
    const keys = o.order ? o.order.filter((k) => groups.has(k)) : Array.from(groups.keys()).sort();
    const panelWidth = (o.width - o.gap * (o.columns - 1)) / o.columns;

    const xDomain = o.xDomain || padded.apply(null, S.extent(points, (p) => p.x));
    const yDomain = o.yDomain || padded.apply(null, S.extent(points, (p) => p.y));

    const panelOptions = {
      width: panelWidth, height: o.panelHeight,
      padTop: 22, padRight: 8, padBottom: 26, padLeft: 40,
      radius: 4, xTickCount: 3, yTickCount: 3,
      xDomain: xDomain, yDomain: yDomain,
    };
    const contextSpec = S.scatterSpec(points, panelOptions);

    return keys.map(function (key, i) {
      const col = i % o.columns;
      const row = Math.floor(i / o.columns);
      const spec = S.scatterSpec(groups.get(key), panelOptions);
      return {
        key: key,
        spec: spec,
        marks: spec.marks,
        contextMarks: contextSpec.marks,
        col: col,
        row: row,
        x: col * (panelWidth + o.gap),
        y: row * (o.panelHeight + o.gap),
      };
    });
  };

  S.drawScatter = function (spec, options) {
    const o = options || {};
    const svg = S.svgRoot(spec, o.ariaLabel || "Scatter plot");
    svg.appendChild(S.drawAxisY(spec, o.yFormat || S.fmtCompact));
    svg.appendChild(S.drawAxisX(spec, o.xFormat || S.fmtCompact));
    svg.appendChild(S.axisTitle(o.xTitle, (spec.plotLeft + spec.plotRight) / 2, spec.height - 4));
    svg.appendChild(S.axisTitle(o.yTitle, 14, (spec.plotTop + spec.plotBottom) / 2, "middle", true));

    const cloud = S.svgEl("g", { class: "cloud" });
    for (const mark of spec.marks) {
      cloud.appendChild(S.svgEl("circle", {
        cx: mark.cx, cy: mark.cy, r: mark.r + 2, fill: "var(--surface-1)",
      }));
      cloud.appendChild(S.svgEl("circle", {
        class: "mark", "data-key": mark.key,
        cx: mark.cx, cy: mark.cy, r: mark.r,
        fill: o.colorOf ? o.colorOf(mark) : "var(--series-1)",
      }));
    }
    svg.appendChild(cloud);

    for (const mark of spec.marks.filter((m) => (o.labelled || []).indexOf(m.key) >= 0)) {
      svg.appendChild(S.svgEl("text", {
        class: "value-label",
        x: mark.cx + mark.r + 6, y: mark.cy + 4, text: mark.label,
      }));
    }

    // One transparent surface carries hover for the whole cloud; the nearest
    // point wins, so an 8px dot never has to be hit dead-centre.
    const surface = S.svgEl("rect", {
      class: "hit",
      x: spec.plotLeft, y: spec.plotTop,
      width: spec.plotRight - spec.plotLeft,
      height: spec.plotBottom - spec.plotTop,
    });
    surface.addEventListener("pointermove", function (event) {
      const mark = S.nearestMark(spec, event.offsetX, event.offsetY);
      if (mark) { S.showTip(o.tip(mark)); S.moveTip(event); }
    });
    surface.addEventListener("pointerleave", () => S.hideTip());
    svg.appendChild(surface);
    return svg;
  };

  S.drawFacets = function (facets, options) {
    const o = options || {};
    const columns = o.columns || 4;
    const last = facets[facets.length - 1];
    const outer = {
      width: o.width,
      height: last ? last.y + last.spec.height : 0,
      plotLeft: 0, plotRight: o.width,
      padTop: 0, padBottom: 0, ticks: [],
    };
    const svg = S.svgRoot(outer, o.ariaLabel || "Small multiples");

    for (const facet of facets) {
      const group = S.svgEl("g", {
        class: "facet", "data-key": facet.key,
        transform: "translate(" + facet.x + "," + facet.y + ")",
      });
      group.appendChild(S.svgEl("text", {
        class: "facet-title", x: facet.spec.plotLeft, y: 12,
        text: facet.key + " · " + facet.marks.length,
      }));
      group.appendChild(S.drawAxisY(facet.spec, o.yFormat || S.fmtCompact));
      group.appendChild(S.drawAxisX(facet.spec, o.xFormat || S.fmt1));

      for (const mark of facet.contextMarks) {
        group.appendChild(S.svgEl("circle", {
          class: "context-dot", cx: mark.cx, cy: mark.cy, r: 2,
        }));
      }
      for (const mark of facet.marks) {
        group.appendChild(S.svgEl("circle", {
          cx: mark.cx, cy: mark.cy, r: mark.r + 2, fill: "var(--surface-1)",
        }));
        group.appendChild(S.svgEl("circle", {
          class: "mark", "data-key": mark.key,
          cx: mark.cx, cy: mark.cy, r: mark.r, fill: o.colorOf(facet.key),
        }));
      }

      const surface = S.svgEl("rect", {
        class: "hit",
        x: facet.spec.plotLeft, y: facet.spec.plotTop,
        width: facet.spec.plotRight - facet.spec.plotLeft,
        height: facet.spec.plotBottom - facet.spec.plotTop,
        tabindex: "0",
        "aria-label": facet.key + ": " + facet.marks.length + " cities",
      });
      surface.addEventListener("pointermove", function (event) {
        const mark = S.nearestMark(facet.spec, event.offsetX - facet.x, event.offsetY - facet.y);
        if (mark) { S.showTip(o.tip(mark)); S.moveTip(event); }
      });
      surface.addEventListener("pointerleave", () => S.hideTip());
      if (o.onSelect) surface.addEventListener("click", () => o.onSelect(facet.key));
      group.appendChild(surface);
      svg.appendChild(group);
    }
    return svg;
  };

  S.register({
    id: "installations-vs-roi",
    page: "financial",
    title: "Where solar is installed against where it pays back",
    definition:
      "Solar_Installations_Count on a square-root axis against ROI_Percentage. " +
      "One dot per city; the correlation is quoted from the build, not refitted here.",
    wide: true,
    render: function (container, ctx) {
      const points = ctx.cities.map((c) => ({
        key: c.city, label: c.city, x: Math.sqrt(c.installations), y: c.roi_pct, meta: c,
      }));
      const spec = S.scatterSpec(points, { width: 700, height: 340, padLeft: 64 });
      container.appendChild(S.drawScatter(spec, {
        ariaLabel: "Installations against return on investment, one dot per city",
        xTitle: "Installations (square-root scale)",
        yTitle: "ROI %",
        xFormat: (v) => S.fmtCompact(Math.round(v * v)),
        yFormat: (v) => S.fmt1(v) + "%",
        labelled: ["Phoenix", "Dubai", "Cairo"],
        tip: (mark) => ({
          value: S.fmt1(mark.meta.roi_pct) + "% ROI",
          label: mark.meta.city + ", " + mark.meta.country,
          rows: [
            ["Installations", S.fmtInt(mark.meta.installations)],
            ["Region", mark.meta.region],
          ],
        }),
      }));
    },
    callout: (ctx) =>
      "Correlation between installations and ROI is " +
      ctx.payload.correlations.installations_vs_roi +
      " — close to nothing. The largest deployments are in China, India and Europe; " +
      "the best returns are in Phoenix, Dubai and Cairo. Installed capacity is not " +
      "following the return.",
    table: (ctx) => ({
      caption: "Installations against ROI",
      columns: ["City", "Region", "Installations", "ROI %"],
      rows: ctx.cities.map((c) => [c.city, c.region, S.fmtInt(c.installations), S.fmt1(c.roi_pct)]),
    }),
  });

  S.register({
    id: "ghi-vs-production",
    page: "production",
    title: "Irradiance against production, region by region",
    definition:
      "GHI_kWh_per_m2 against Avg_Annual_Production_kWh, one panel per region on " +
      "shared axes. Grey dots are all 48 cities, for context; coloured dots are the panel's region.",
    wide: true,
    render: function (container, ctx) {
      const points = ctx.cities.map((c) => ({
        key: c.city, label: c.city, x: c.ghi, y: c.production_kwh, meta: c,
      }));
      const facets = S.facetSpecs(points, {
        facetOf: (p) => p.meta.region,
        order: ctx.allRegions,
        width: 700, columns: 4, panelHeight: 160, gap: 18,
      });
      container.appendChild(S.drawFacets(facets, {
        width: 700, columns: 4,
        ariaLabel: "Irradiance against annual production, one panel per region",
        xFormat: S.fmt1,
        yFormat: S.fmtCompact,
        colorOf: (region) => S.regionColorVar(region, ctx.allRegions),
        onSelect: (region) => ctx.isolate("regions", region),
        tip: (mark) => ({
          value: S.fmtInt(mark.meta.production_kwh) + " kWh/yr",
          label: mark.meta.city + ", " + mark.meta.country,
          rows: [
            ["GHI", S.fmt1(mark.meta.ghi) + " kWh/m²"],
            ["Sunlight", S.fmtInt(mark.meta.sunlight_hours) + " hrs/yr"],
          ],
        }),
      }));
    },
    callout: (ctx) =>
      "Irradiance and production correlate at " + ctx.payload.correlations.ghi_vs_production +
      ". This is the one relationship in the dataset that is physical rather than " +
      "arithmetic — the rest of the money columns are rescalings of production.",
    table: (ctx) => ({
      caption: "Irradiance and production by city",
      columns: ["City", "Region", "GHI kWh/m²", "kWh/yr"],
      rows: ctx.cities.map((c) => [c.city, c.region, S.fmt1(c.ghi), S.fmtInt(c.production_kwh)]),
    }),
  });

  S.register({
    id: "roi-vs-viability",
    page: "sustainability",
    title: "ROI against the supplied viability score",
    definition:
      "ROI_Percentage against Solar_Viability_Score. Kept because the near-perfect " +
      "fit is itself the finding: the score adds no information ROI does not already carry.",
    render: function (container, ctx) {
      const points = ctx.cities.map((c) => ({
        key: c.city, label: c.city, x: c.viability, y: c.roi_pct, meta: c,
      }));
      container.appendChild(S.drawScatter(S.scatterSpec(points, { width: 520, height: 320 }), {
        ariaLabel: "Viability score against return on investment",
        xTitle: "Solar viability score",
        yTitle: "ROI %",
        xFormat: S.fmtInt,
        yFormat: (v) => S.fmt1(v) + "%",
        labelled: ["Phoenix"],
        tip: (mark) => ({
          value: S.fmt1(mark.meta.roi_pct) + "% ROI",
          label: mark.meta.city,
          rows: [["Viability score", S.fmtInt(mark.meta.viability)]],
        }),
      }));
    },
    callout: (ctx) =>
      "These two columns correlate at " + ctx.payload.correlations.roi_vs_viability +
      ". Treat the viability score as a restatement of ROI, not as a second opinion.",
    table: (ctx) => ({
      caption: "Viability score against ROI",
      columns: ["City", "Viability", "ROI %"],
      rows: ctx.cities.map((c) => [c.city, S.fmtInt(c.viability), S.fmt1(c.roi_pct)]),
    }),
  });
})(globalThis.SOLAR);
```

The installations axis is square-rooted because installations span 150 to 609,000; on a linear axis 44 of 48 cities collapse against the left edge and the chart shows nothing. The axis title says so, and the tick labels are printed back in real installation counts.

- [ ] **Step 5: Run test to verify it passes**

Run: `node --test tests/js/scatter.test.mjs`
Expected: 14 pass, 0 fail

- [ ] **Step 6: Register, rebuild, and look at it**

Insert `"js/charts_scatter.js"` into `ASSET_ORDER` before `"js/app.js"`.

Run: `python -m pytest tests/ -q` and `node --test "tests/js/*.test.mjs"` — all pass
Run: `python -m analysis.build_dashboard`

Open the page. Expected: page 1 gains the installations/ROI cloud with Phoenix, Dubai and Cairo labelled and the 0.137 callout beneath; page 2 gains seven region panels on shared axes; page 3 gains the viability cloud. Check by eye that facet titles do not collide with the panel above and that no axis label is clipped.

- [ ] **Step 7: Commit**

```bash
git add analysis/dashboard_assets analysis/build_dashboard.py tests/js/scatter.test.mjs
git -c user.name="chinm" -c user.email="mishraswagat2804@gmail.com" commit -m "feat: add scatter clouds and the faceted irradiance small-multiple"
```

---

### Task 8: The world map

**Files:**
- Create: `analysis/dashboard_assets/js/charts_map.js`
- Modify: `analysis/build_dashboard.py` (`ASSET_ORDER`)
- Create: `tests/js/map.test.mjs`

**Interfaces:**
- Consumes: `SOLAR.svgRoot`, `svgEl`, `attachTip`, `register`
- Produces on `SOLAR`:
  - `project(lat, lon, width, height) -> {x, y}` — equirectangular, `lon −180…180` onto `0…width`, `lat 90…−90` onto `0…height`
  - `bubbleRadius(value, maxValue, rMin, rMax) -> number` — area-proportional (`r ∝ √value`)
  - `mapSpec(cities, opts) -> {marks, graticule, guides, width, height}`
  - `drawMap(spec, opts) -> SVGElement`
- Registers `world-map` (sustainability, wide).

There is no basemap: a coastline file is tens of kilobytes of geometry for a decorative outline, and no external request is permitted. Context comes from a labelled graticule — meridians and parallels every 30°, with the equator and both tropics drawn as named guides. That is honest about what the projection is and costs nothing. Bubbles are area-proportional, so radius scales with the square root of installations; scaling radius linearly would overstate China by a factor of forty.

- [ ] **Step 1: Write the failing test**

Create `tests/js/map.test.mjs`:

```js
import test from "node:test";
import assert from "node:assert/strict";
import { load, payload } from "./load.mjs";

const S = load("boot.js", "core.js", "rollup.js", "filters.js", "render.js", "charts_map.js");
const data = payload();

test("the projection puts null island at the centre", () => {
  assert.deepEqual(S.project(0, 0, 720, 360), { x: 360, y: 180 });
});

test("the projection puts the corners at the corners", () => {
  assert.deepEqual(S.project(90, -180, 720, 360), { x: 0, y: 0 });
  assert.deepEqual(S.project(-90, 180, 720, 360), { x: 720, y: 360 });
});

test("north is up", () => {
  const oslo = S.project(59.91, 10.75, 720, 360);
  const sydney = S.project(-33.87, 151.21, 720, 360);
  assert.ok(oslo.y < sydney.y);
  assert.ok(oslo.x < sydney.x);
});

test("bubble area, not radius, is proportional to the value", () => {
  const big = S.bubbleRadius(100, 100, 0, 10);
  const quarter = S.bubbleRadius(25, 100, 0, 10);
  assert.equal(big, 10);
  assert.equal(quarter, 5);
});

test("a zero value still gets a visible minimum bubble", () => {
  assert.equal(S.bubbleRadius(0, 100, 3, 10), 3);
});

test("a zero maximum does not divide by zero", () => {
  assert.ok(Number.isFinite(S.bubbleRadius(0, 0, 3, 10)));
});

test("every city lands inside the frame", () => {
  const spec = S.mapSpec(data.cities, { width: 720, height: 360 });
  assert.equal(spec.marks.length, 48);
  for (const mark of spec.marks) {
    assert.ok(mark.cx >= 0 && mark.cx <= 720, mark.key + " x");
    assert.ok(mark.cy >= 0 && mark.cy <= 360, mark.key + " y");
  }
});

test("the largest deployment gets the largest bubble", () => {
  const spec = S.mapSpec(data.cities, { width: 720, height: 360 });
  const biggest = spec.marks.slice().sort((a, b) => b.r - a.r)[0];
  const expected = data.cities.slice().sort((a, b) => b.installations - a.installations)[0];
  assert.equal(biggest.key, expected.city);
});

test("bubbles are drawn largest first so small ones stay clickable", () => {
  const spec = S.mapSpec(data.cities, { width: 720, height: 360 });
  const radii = spec.marks.map((m) => m.r);
  assert.deepEqual(radii, radii.slice().sort((a, b) => b - a));
});

test("the graticule spans the frame every thirty degrees", () => {
  const spec = S.mapSpec(data.cities, { width: 720, height: 360 });
  assert.equal(spec.graticule.meridians.length, 13);
  assert.equal(spec.graticule.parallels.length, 7);
});

test("the equator and both tropics are named guides", () => {
  const spec = S.mapSpec(data.cities, { width: 720, height: 360 });
  assert.deepEqual(spec.guides.map((g) => g.label), ["Tropic of Cancer", "Equator", "Tropic of Capricorn"]);
  const equator = spec.guides.find((g) => g.label === "Equator");
  assert.equal(equator.y, 180);
});

test("an empty city list produces a map with a graticule and no bubbles", () => {
  const spec = S.mapSpec([], { width: 720, height: 360 });
  assert.deepEqual(spec.marks, []);
  assert.equal(spec.graticule.meridians.length, 13);
});

test("the map chart is registered on the sustainability page", () => {
  const chart = S.charts.find((c) => c.id === "world-map");
  assert.ok(chart);
  assert.equal(chart.page, "sustainability");
  assert.ok(chart.definition.includes("quirectangular"));
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/js/map.test.mjs`
Expected: FAIL — `ENOENT` on `charts_map.js`

- [ ] **Step 3: Write the implementation**

Create `analysis/dashboard_assets/js/charts_map.js`:

```js
/* charts_map.js — equirectangular city map, bubbles sized by installations.
   No basemap: a coastline is decoration that cannot be fetched anyway. The
   graticule and the named tropics carry the geography instead. */
(function (S) {
  "use strict";

  const R_MIN = 3;
  const R_MAX = 26;
  const GUIDES = [
    { lat: 23.44, label: "Tropic of Cancer" },
    { lat: 0, label: "Equator" },
    { lat: -23.44, label: "Tropic of Capricorn" },
  ];

  S.project = function (lat, lon, width, height) {
    return {
      x: ((lon + 180) / 360) * width,
      y: ((90 - lat) / 180) * height,
    };
  };

  S.bubbleRadius = function (value, maxValue, rMin, rMax) {
    if (!(maxValue > 0)) return rMin;
    return rMin + (rMax - rMin) * Math.sqrt(Math.max(0, value) / maxValue);
  };

  S.mapSpec = function (cities, options) {
    const o = Object.assign({ width: 720, height: 360, rMin: R_MIN, rMax: R_MAX }, options || {});
    const maxInstallations = cities.length
      ? Math.max.apply(null, cities.map((c) => c.installations))
      : 0;

    const marks = cities.map(function (city) {
      const point = S.project(city.lat, city.lon, o.width, o.height);
      return {
        key: city.city,
        label: city.city + ", " + city.country,
        cx: point.x,
        cy: point.y,
        r: S.bubbleRadius(city.installations, maxInstallations, o.rMin, o.rMax),
        meta: city,
      };
    });
    // Largest first: a small bubble drawn under a large one is unreachable.
    marks.sort((a, b) => b.r - a.r || a.key.localeCompare(b.key));

    const meridians = [];
    for (let lon = -180; lon <= 180; lon += 30) {
      meridians.push({ lon: lon, x: S.project(0, lon, o.width, o.height).x });
    }
    const parallels = [];
    for (let lat = -90; lat <= 90; lat += 30) {
      parallels.push({ lat: lat, y: S.project(lat, 0, o.width, o.height).y });
    }

    return {
      marks: marks,
      graticule: { meridians: meridians, parallels: parallels },
      guides: GUIDES.map((g) => ({
        label: g.label, lat: g.lat, y: S.project(g.lat, 0, o.width, o.height).y,
      })),
      width: o.width,
      height: o.height,
      maxInstallations: maxInstallations,
      padTop: 0,
      padBottom: 0,
      plotLeft: 0,
      plotRight: o.width,
      ticks: [],
    };
  };

  S.drawMap = function (spec, options) {
    const o = options || {};
    const svg = S.svgRoot(spec, o.ariaLabel || "World map of solar installations");

    const grid = S.svgEl("g", { class: "graticule" });
    for (const meridian of spec.graticule.meridians) {
      grid.appendChild(S.svgEl("line", {
        class: "gridline", x1: meridian.x, x2: meridian.x, y1: 0, y2: spec.height,
      }));
    }
    for (const parallel of spec.graticule.parallels) {
      grid.appendChild(S.svgEl("line", {
        class: "gridline", x1: 0, x2: spec.width, y1: parallel.y, y2: parallel.y,
      }));
    }
    svg.appendChild(grid);

    for (const guide of spec.guides) {
      svg.appendChild(S.svgEl("line", {
        class: "axis-line", x1: 0, x2: spec.width, y1: guide.y, y2: guide.y,
      }));
      svg.appendChild(S.svgEl("text", {
        class: "note", x: 6, y: guide.y - 5, text: guide.label,
      }));
    }

    for (const mark of spec.marks) {
      const group = S.svgEl("g", { class: "mark", "data-key": mark.key });
      group.appendChild(S.svgEl("circle", {
        cx: mark.cx, cy: mark.cy, r: mark.r,
        fill: "var(--series-1)", "fill-opacity": "0.32",
      }));
      group.appendChild(S.svgEl("circle", {
        cx: mark.cx, cy: mark.cy, r: 2.5, fill: "var(--series-1)",
      }));
      const hit = S.svgEl("circle", {
        class: "hit",
        cx: mark.cx, cy: mark.cy, r: Math.max(12, mark.r),
        tabindex: "0",
        "aria-label": mark.label + ": " + S.fmtInt(mark.meta.installations) + " installations",
      });
      S.attachTip(hit, () => o.tip(mark));
      if (o.onSelect) hit.addEventListener("click", () => o.onSelect(mark));
      group.appendChild(hit);
      svg.appendChild(group);
    }
    return svg;
  };

  S.register({
    id: "world-map",
    page: "sustainability",
    title: "Where the 48 cities are",
    definition:
      "Equirectangular projection of Latitude and Longitude. Bubble area — not " +
      "radius — is proportional to Solar_Installations_Count. No basemap: the " +
      "graticule and tropics carry the geography.",
    wide: true,
    render: function (container, ctx) {
      const spec = S.mapSpec(ctx.cities, { width: 720, height: 360 });
      container.appendChild(S.drawMap(spec, {
        ariaLabel: "World map, bubble area proportional to installations",
        onSelect: (mark) => ctx.isolate("regions", mark.meta.region),
        tip: (mark) => ({
          value: S.fmtInt(mark.meta.installations) + " installations",
          label: mark.label,
          rows: [
            ["Region", mark.meta.region],
            ["ROI", S.fmt1(mark.meta.roi_pct) + "%"],
            ["CO₂ avoided", S.fmt2(mark.meta.co2_tons) + " t/yr"],
          ],
        }),
      }));
    },
    table: (ctx) => ({
      caption: "Cities by location and installed count",
      columns: ["City", "Country", "Latitude", "Longitude", "Installations"],
      rows: ctx.cities.map((c) => [
        c.city, c.country, S.fmt2(c.lat), S.fmt2(c.lon), S.fmtInt(c.installations),
      ]),
    }),
  });
})(globalThis.SOLAR);
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test tests/js/map.test.mjs`
Expected: 13 pass, 0 fail

- [ ] **Step 5: Register, rebuild, and look at it**

Insert `"js/charts_map.js"` into `ASSET_ORDER` before `"js/app.js"`.

Run: `python -m pytest tests/ -q` and `node --test "tests/js/*.test.mjs"` — all pass
Run: `python -m analysis.build_dashboard`

Open page 3. Expected: a recognisable world scatter — a European cluster, a North American arc, Sydney and Melbourne low-right — with China's bubble the largest. Confirm the graticule reads as recessive hairlines and the tropic labels do not sit on top of a bubble in the Atlantic.

- [ ] **Step 6: Commit**

```bash
git add analysis/dashboard_assets analysis/build_dashboard.py tests/js/map.test.mjs
git -c user.name="chinm" -c user.email="mishraswagat2804@gmail.com" commit -m "feat: add the equirectangular world map with area-proportional bubbles"
```

---

### Task 9: The expandable matrix and the real tooltip layer

**Files:**
- Create: `analysis/dashboard_assets/js/charts_matrix.js`
- Modify: `analysis/dashboard_assets/js/render.js` (replace the tooltip stubs)
- Modify: `analysis/dashboard_assets/css/dashboard.css` (append matrix rules)
- Modify: `analysis/build_dashboard.py` (`ASSET_ORDER`)
- Create: `tests/js/matrix.test.mjs`
- Create: `tests/js/tooltip.test.mjs`

**Interfaces:**
- Consumes: `SOLAR.el`, `fmt*`, `regionColorVar`, `register`, `groupBy`
- Produces on `SOLAR`:
  - `MATRIX_COLUMNS: string[]`
  - `matrixRows(regions, countries, cities) -> [{level, key, parent, label, cells, hasChildren}]`
  - `drawMatrix(rows, opts) -> HTMLTableElement`
  - `showTip(model)`, `hideTip()`, `moveTip(event)`, `ensureTip()` — replacing the Task 5 stubs
- Registers `region-country-city` (sustainability, wide).

The matrix is the reference dashboard's one genuinely useful table, and the one it rendered as `26 64`. Every number here goes through the `en-US` formatters, and the United States row must read `26.64`.

Tooltip contract: value first in strong type, label second; rows keyed by a short line of the series colour; all text inserted with `textContent`, because city and country names are CSV data. The tooltip never carries a value that is not also in the table twin.

- [ ] **Step 1: Write the failing matrix test**

Create `tests/js/matrix.test.mjs`:

```js
import test from "node:test";
import assert from "node:assert/strict";
import { load, payload } from "./load.mjs";
import { makeDocument } from "./fakedom.mjs";

const S = load(
  "boot.js", "core.js", "rollup.js", "filters.js", "render.js", "charts_matrix.js"
);
const data = payload();
S.useDocument(makeDocument(data));

const rows = () => S.matrixRows(data.regions, data.countries, data.cities);

test("the matrix holds every region, country and city exactly once", () => {
  const all = rows();
  assert.equal(all.filter((r) => r.level === 0).length, 7);
  assert.equal(all.filter((r) => r.level === 1).length, 30);
  assert.equal(all.filter((r) => r.level === 2).length, 48);
  assert.equal(all.length, 85);
});

test("countries sit under their own region and cities under their own country", () => {
  const all = rows();
  const byKey = new Map(all.map((r) => [r.key, r]));
  for (const row of all) {
    if (row.level === 0) { assert.equal(row.parent, null); continue; }
    const parent = byKey.get(row.parent);
    assert.ok(parent, row.label + " has no parent row");
    assert.equal(parent.level, row.level - 1);
  }
});

test("a region's children follow it before the next region begins", () => {
  const all = rows();
  const firstRegion = all[0];
  assert.equal(firstRegion.level, 0);
  assert.equal(all[1].parent, firstRegion.key);
});

test("decimals render with a dot, never a space", () => {
  const usa = rows().find((r) => r.label === "United States" && r.level === 1);
  assert.ok(usa.cells.includes("26.64"), usa.cells.join(" | "));
});

test("leaf rows are marked as having no children", () => {
  const all = rows();
  assert.ok(all.filter((r) => r.level === 2).every((r) => r.hasChildren === false));
  assert.ok(all.filter((r) => r.level === 0).every((r) => r.hasChildren === true));
});

test("a single-city region still expands to its one country and city", () => {
  // Middle East holds only Tel Aviv, Israel — Dubai is labelled Asia.
  const all = rows();
  const index = all.findIndex((r) => r.level === 0 && r.label === "Middle East");
  assert.equal(all[index + 1].level, 1);
  assert.equal(all[index + 1].label, "Israel");
  assert.equal(all[index + 2].level, 2);
  assert.equal(all[index + 2].label, "Tel Aviv");
  assert.equal(all[index + 3].level, 0, "the next region begins straight after");
});

test("only region rows are visible before anything is expanded", () => {
  const table = S.drawMatrix(rows(), { onSelect: () => {} });
  const bodyRows = table.querySelectorAll("tr").filter((tr) => tr.getAttribute("data-level"));
  assert.equal(bodyRows.filter((tr) => !tr.hidden).length, 7);
});

test("expanding a region reveals its countries but not their cities", () => {
  const table = S.drawMatrix(rows(), { onSelect: () => {} });
  const all = table.querySelectorAll("tr").filter((tr) => tr.getAttribute("data-level"));
  const europe = all.find((tr) => tr.getAttribute("data-key") === "region:Europe");
  europe.querySelector("button").dispatch("click");

  const visible = all.filter((tr) => !tr.hidden);
  assert.equal(visible.filter((tr) => tr.getAttribute("data-level") === "1").length,
    data.countries.filter((c) => c.region === "Europe").length);
  assert.equal(visible.filter((tr) => tr.getAttribute("data-level") === "2").length, 0);
});

test("collapsing a region hides its descendants again", () => {
  const table = S.drawMatrix(rows(), { onSelect: () => {} });
  const all = table.querySelectorAll("tr").filter((tr) => tr.getAttribute("data-level"));
  const europe = all.find((tr) => tr.getAttribute("data-key") === "region:Europe");
  europe.querySelector("button").dispatch("click");
  europe.querySelector("button").dispatch("click");
  assert.equal(all.filter((tr) => !tr.hidden).length, 7);
});

test("the expand control reports its state to assistive technology", () => {
  const table = S.drawMatrix(rows(), { onSelect: () => {} });
  const europe = table
    .querySelectorAll("tr")
    .find((tr) => tr.getAttribute("data-key") === "region:Europe");
  const button = europe.querySelector("button");
  assert.equal(button.getAttribute("aria-expanded"), "false");
  button.dispatch("click");
  assert.equal(button.getAttribute("aria-expanded"), "true");
});

test("the matrix chart is registered on the sustainability page", () => {
  const chart = S.charts.find((c) => c.id === "region-country-city");
  assert.ok(chart);
  assert.equal(chart.page, "sustainability");
});
```

- [ ] **Step 2: Write the failing tooltip test**

Create `tests/js/tooltip.test.mjs`:

```js
import test from "node:test";
import assert from "node:assert/strict";
import { load, payload } from "./load.mjs";
import { makeDocument } from "./fakedom.mjs";

const S = load("boot.js", "core.js", "rollup.js", "filters.js", "render.js");
const doc = makeDocument(payload());
S.useDocument(doc);

test("the tooltip element is created once and reused", () => {
  const first = S.ensureTip();
  const second = S.ensureTip();
  assert.equal(first, second);
  assert.equal(doc.body.querySelectorAll(".tooltip").length, 1);
});

test("the value leads and the label follows", () => {
  S.showTip({ value: "17.2% ROI", label: "Phoenix, United States", rows: [] });
  const tip = S.ensureTip();
  assert.match(tip.querySelector(".tip-value").textContent, /17\.2% ROI/);
  assert.match(tip.querySelector(".tip-label").textContent, /Phoenix/);
});

test("detail rows render as label and value pairs", () => {
  S.showTip({
    value: "6.30 t", label: "Dubai",
    rows: [["Region", "Asia"], ["Installations", "850"]],
  });
  const tip = S.ensureTip();
  assert.equal(tip.querySelectorAll(".tip-row").length, 2);
  assert.match(tip.textContent, /Installations/);
  assert.match(tip.textContent, /850/);
});

test("labels go in as text, never as markup", () => {
  S.showTip({ value: "1", label: "<img onerror=alert(1)>", rows: [] });
  const tip = S.ensureTip();
  assert.equal(tip.querySelector(".tip-label").textContent, "<img onerror=alert(1)>");
  assert.equal(tip.querySelectorAll("img").length, 0);
});

test("showing then hiding leaves the tooltip hidden", () => {
  S.showTip({ value: "1", label: "x", rows: [] });
  assert.equal(S.ensureTip().hidden, false);
  S.hideTip();
  assert.equal(S.ensureTip().hidden, true);
});

test("a tooltip with no detail rows still renders", () => {
  assert.doesNotThrow(() => S.showTip({ value: "1", label: "x" }));
});
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `node --test tests/js/matrix.test.mjs tests/js/tooltip.test.mjs`
Expected: FAIL — `ENOENT` on `charts_matrix.js`, and `S.ensureTip is not a function`

- [ ] **Step 4: Replace the tooltip stubs in `render.js`**

Delete the three stub lines added in Task 5 (`S.showTip = function () {};` and its two neighbours) and put this in their place:

```js
  S.ensureTip = function () {
    const doc = S.doc();
    let tip = doc.getElementById("solar-tooltip");
    if (!tip) {
      tip = S.el("div", { class: "tooltip", id: "solar-tooltip", role: "status" });
      tip.hidden = true;
      doc.body.appendChild(tip);
    }
    return tip;
  };

  S.showTip = function (model) {
    const tip = S.ensureTip();
    S.clear(tip);
    tip.appendChild(S.el("div", { class: "tip-value", text: model.value }));
    tip.appendChild(S.el("div", { class: "tip-label", text: model.label }));
    for (const [label, value] of model.rows || []) {
      tip.appendChild(S.el("div", { class: "tip-row" }, [
        S.el("span", { class: "tip-row-label", text: label }),
        S.el("span", { class: "tip-row-value", text: value }),
      ]));
    }
    tip.hidden = false;
    return tip;
  };

  S.hideTip = function () {
    const tip = S.ensureTip();
    tip.hidden = true;
    return tip;
  };

  S.moveTip = function (event) {
    const tip = S.ensureTip();
    if (!tip.style) return tip;
    const x = (event && event.clientX) || 0;
    const y = (event && event.clientY) || 0;
    // Flip before the pointer near the right edge so the tip never leaves the viewport.
    const flip = typeof globalThis.innerWidth === "number" && x > globalThis.innerWidth - 280;
    tip.style.left = (flip ? x - 268 : x + 16) + "px";
    tip.style.top = y + 16 + "px";
    return tip;
  };
```

- [ ] **Step 5: Append the matrix and tooltip styles**

Add to `analysis/dashboard_assets/css/dashboard.css`:

```css
.matrix { width: 100%; border-collapse: collapse; font-size: 13px; font-variant-numeric: tabular-nums; }
.matrix th, .matrix td { text-align: right; padding: 6px 10px; border-bottom: 1px solid var(--hairline); }
.matrix th:first-child, .matrix td:first-child { text-align: left; }
.matrix thead th { color: var(--text-muted); font-weight: 600; font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; }
.matrix tr[data-level="0"] { font-weight: 650; }
.matrix tr[data-level="1"] td:first-child, .matrix tr[data-level="1"] th:first-child { padding-left: 30px; }
.matrix tr[data-level="2"] { color: var(--text-secondary); }
.matrix tr[data-level="2"] td:first-child, .matrix tr[data-level="2"] th:first-child { padding-left: 54px; }
.matrix .twist {
  font: inherit; color: var(--text-muted); background: transparent;
  border: 0; cursor: pointer; padding: 0 8px 0 0; width: 22px; text-align: left;
}
.matrix .region-key { display: inline-block; width: 8px; height: 8px; border-radius: 2px; margin-right: 8px; }
.tip-row { display: flex; justify-content: space-between; gap: 16px; margin-top: 4px; }
.tip-row-label { color: var(--text-secondary); }
.tip-row-value { font-variant-numeric: tabular-nums; }
```

- [ ] **Step 6: Write the matrix module**

Create `analysis/dashboard_assets/js/charts_matrix.js`:

```js
/* charts_matrix.js — region → country → city, expandable.
   Every number goes through the en-US formatters: the reference dashboard
   printed 26.64 as "26 64", which is what a locale-dependent separator does. */
(function (S) {
  "use strict";

  S.MATRIX_COLUMNS = ["Region · country · city", "Cities", "CO₂ t/yr", "Installations", "kWh/yr"];

  S.matrixRows = function (regions, countries, cities) {
    const citiesByCountry = S.groupBy(cities, (c) => c.country);
    const rows = [];

    for (const region of regions) {
      const regionKey = "region:" + region.region;
      rows.push({
        level: 0,
        key: regionKey,
        parent: null,
        label: region.region,
        region: region.region,
        hasChildren: true,
        cells: [
          S.fmtInt(region.cities),
          S.fmt2(region.co2_tons),
          S.fmtInt(region.installations),
          S.fmtInt(region.production_kwh),
        ],
      });

      const inRegion = countries.filter((c) => c.region === region.region);
      for (const country of inRegion) {
        const countryKey = "country:" + country.country;
        const own = citiesByCountry.get(country.country) || [];
        rows.push({
          level: 1,
          key: countryKey,
          parent: regionKey,
          label: country.country,
          region: region.region,
          hasChildren: own.length > 0,
          cells: [
            S.fmtInt(country.cities),
            S.fmt2(country.co2_tons),
            S.fmtInt(country.installations),
            S.fmtInt(own.reduce((sum, c) => sum + c.production_kwh, 0)),
          ],
        });

        for (const city of own) {
          rows.push({
            level: 2,
            key: "city:" + city.city,
            parent: countryKey,
            label: city.city,
            region: region.region,
            hasChildren: false,
            cells: [
              "1",
              S.fmt2(city.co2_tons),
              S.fmtInt(city.installations),
              S.fmtInt(city.production_kwh),
            ],
          });
        }
      }
    }
    return rows;
  };

  S.drawMatrix = function (rows, options) {
    const o = options || {};
    const expanded = new Set();
    const elements = new Map();

    function visible(row) {
      let parent = row.parent;
      while (parent) {
        if (!expanded.has(parent)) return false;
        const parentRow = rows.find((r) => r.key === parent);
        parent = parentRow ? parentRow.parent : null;
      }
      return true;
    }

    function refresh() {
      for (const row of rows) {
        const tr = elements.get(row.key);
        tr.hidden = !visible(row);
        const button = tr.querySelector("button");
        if (button) button.setAttribute("aria-expanded", String(expanded.has(row.key)));
      }
    }

    const body = S.el("tbody");
    for (const row of rows) {
      const first = S.el("th", { scope: "row" });

      if (row.hasChildren) {
        const twist = S.el("button", {
          type: "button", class: "twist",
          "aria-expanded": "false",
          "aria-label": "Expand " + row.label,
          text: "▸",
        });
        twist.addEventListener("click", function () {
          if (expanded.has(row.key)) expanded.delete(row.key);
          else expanded.add(row.key);
          twist.textContent = expanded.has(row.key) ? "▾" : "▸";
          refresh();
        });
        first.appendChild(twist);
      }

      if (row.level === 0 && o.colorOf) {
        first.appendChild(S.el("span", {
          class: "region-key", style: "background:" + o.colorOf(row.region),
        }));
      }
      first.appendChild(S.el("span", { text: row.label }));

      const tr = S.el("tr", { "data-level": String(row.level), "data-key": row.key },
        [first].concat(row.cells.map((cell) => S.el("td", { text: cell }))));
      elements.set(row.key, tr);
      body.appendChild(tr);
    }

    const table = S.el("table", { class: "matrix" }, [
      S.el("caption", { text: o.caption || "Region, country and city detail" }),
      S.el("thead", null, [
        S.el("tr", null, S.MATRIX_COLUMNS.map((c) => S.el("th", { scope: "col", text: c }))),
      ]),
      body,
    ]);
    refresh();
    return table;
  };

  S.register({
    id: "region-country-city",
    page: "sustainability",
    title: "Region, country and city detail",
    definition:
      "Every figure rolled up three ways from the same 48 rows. Expand a region " +
      "to see its countries, a country to see its cities. Totals reconcile exactly.",
    wide: true,
    render: function (container, ctx) {
      container.appendChild(S.drawMatrix(
        S.matrixRows(ctx.regions, ctx.countries, ctx.cities),
        {
          caption: "Region, country and city detail — " + ctx.cities.length + " cities in view",
          colorOf: (region) => S.regionColorVar(region, ctx.allRegions),
        }
      ));
    },
  });
})(globalThis.SOLAR);
```

The matrix has no separate `table` twin: it *is* a table.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `node --test tests/js/matrix.test.mjs tests/js/tooltip.test.mjs`
Expected: 17 pass, 0 fail

- [ ] **Step 8: Register, rebuild, and check the interaction by hand**

Insert `"js/charts_matrix.js"` into `ASSET_ORDER` before `"js/app.js"`.

Run: `python -m pytest tests/ -q` and `node --test "tests/js/*.test.mjs"` — all pass
Run: `python -m analysis.build_dashboard`

Open the page and verify by hand:
- Hovering any bar, dot, scatter cloud or map bubble shows a tooltip with the value in bold and the label under it.
- Tabbing reaches every bar and dot; focus shows the same tooltip as hover.
- On page 3, expanding Middle East → UAE → Dubai shows Dubai's `6.30`.
- The United States row reads `26.64`, not `26 64`.
- The tooltip near the right edge flips to the left of the pointer instead of leaving the window.

- [ ] **Step 9: Commit**

```bash
git add analysis/dashboard_assets analysis/build_dashboard.py tests/js
git -c user.name="chinm" -c user.email="mishraswagat2804@gmail.com" commit -m "feat: add the expandable region matrix and the tooltip layer"
```

---

### Task 10: The signature hero, the final pass, and the docs

**Files:**
- Create: `analysis/dashboard_assets/js/charts_mismatch.js`
- Modify: `analysis/dashboard_assets/css/dashboard.css` (append hero rules)
- Modify: `analysis/build_dashboard.py` (`ASSET_ORDER`)
- Create: `tests/js/mismatch.test.mjs`
- Modify: `tests/test_build.py` (final structural assertions)
- Create: `README.md`
- Modify: `docs/DECISIONS.md`
- Modify: `docs/STATE.md` (intent block only — never the facts block)

**Interfaces:**
- Consumes: `SOLAR.el`, `svgEl`, `svgRoot`, `fmt*`, `regionColorVar`, `register`
- Produces on `SOLAR`:
  - `mismatchSpec(cities, opts) -> {left, right, links, width, height, columnWidth}` where `left`/`right` are `[{key, label, value, rank, x, y, w, h}]` and `links` are `[{key, y1, y2, d}]`
  - `drawMismatch(spec, opts) -> SVGElement`
- Registers `mismatch` (financial, wide) — and must render **first** on page 1.

The hero states the finding the reference dashboard never surfaced: the twelve largest deployments and the twelve best returns are almost disjoint sets. A connector is drawn only for a city that appears in both columns, so the emptiness between the columns is the message. The correlation `0.137` sits between them as the page's single hero figure.

- [ ] **Step 1: Write the failing test**

Create `tests/js/mismatch.test.mjs`:

```js
import test from "node:test";
import assert from "node:assert/strict";
import { load, payload } from "./load.mjs";

const S = load(
  "boot.js", "core.js", "rollup.js", "filters.js", "render.js", "charts_mismatch.js"
);
const data = payload();

const OPTS = { width: 700, count: 12, padTop: 40, rowHeight: 22, columnWidth: 210 };

test("each column holds the requested number of cities", () => {
  const spec = S.mismatchSpec(data.cities, OPTS);
  assert.equal(spec.left.length, 12);
  assert.equal(spec.right.length, 12);
});

test("the left column ranks by installations and the right by ROI", () => {
  const spec = S.mismatchSpec(data.cities, OPTS);
  const installations = spec.left.map((r) => r.value);
  assert.deepEqual(installations, installations.slice().sort((a, b) => b - a));
  assert.equal(spec.right[0].key, "Phoenix");
  assert.equal(spec.right[1].key, "Dubai");
  assert.equal(spec.right[2].key, "Cairo");
});

test("a link exists only for a city in both columns", () => {
  const spec = S.mismatchSpec(data.cities, OPTS);
  const leftKeys = new Set(spec.left.map((r) => r.key));
  const rightKeys = new Set(spec.right.map((r) => r.key));
  const both = [...leftKeys].filter((k) => rightKeys.has(k));
  assert.deepEqual(spec.links.map((l) => l.key).sort(), both.sort());
});

test("the two rankings barely overlap — that is the finding", () => {
  const spec = S.mismatchSpec(data.cities, OPTS);
  assert.ok(spec.links.length <= 3, "overlap was " + spec.links.length + " of 12");
});

test("rows step down one row height at a time", () => {
  const spec = S.mismatchSpec(data.cities, OPTS);
  assert.equal(spec.left[1].y - spec.left[0].y, 22);
  assert.equal(spec.left[0].y, 40);
});

test("the columns sit at opposite edges", () => {
  const spec = S.mismatchSpec(data.cities, OPTS);
  assert.equal(spec.left[0].x, 0);
  assert.equal(spec.right[0].x, 700 - 210);
});

test("each link connects its own two rows", () => {
  const spec = S.mismatchSpec(data.cities, OPTS);
  for (const link of spec.links) {
    const left = spec.left.find((r) => r.key === link.key);
    const right = spec.right.find((r) => r.key === link.key);
    assert.equal(link.y1, left.y + left.h / 2);
    assert.equal(link.y2, right.y + right.h / 2);
    assert.ok(link.d.startsWith("M"), link.d);
    assert.ok(!link.d.includes("NaN"), link.d);
  }
});

test("fewer cities than the requested count does not overrun", () => {
  const spec = S.mismatchSpec(data.cities.slice(0, 4), OPTS);
  assert.equal(spec.left.length, 4);
  assert.equal(spec.right.length, 4);
});

test("an empty city list produces an empty, valid spec", () => {
  const spec = S.mismatchSpec([], OPTS);
  assert.deepEqual(spec.left, []);
  assert.deepEqual(spec.links, []);
  assert.ok(spec.height > 0);
});

test("the hero is registered first on the financial page", () => {
  const financial = S.charts.filter((c) => c.page === "financial");
  assert.equal(financial[0].id, "mismatch");
});

test("the hero quotes the correlation from the payload", () => {
  const chart = S.charts.find((c) => c.id === "mismatch");
  assert.match(chart.callout({ payload: data }), /0\.137/);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/js/mismatch.test.mjs`
Expected: FAIL — `ENOENT` on `charts_mismatch.js`

- [ ] **Step 3: Write the hero module**

Create `analysis/dashboard_assets/js/charts_mismatch.js`:

```js
/* charts_mismatch.js — the page's thesis, drawn.
   Twelve largest deployments on the left, twelve best returns on the right, a
   connector only where a city is in both. The gap is the point. */
(function (S) {
  "use strict";

  const DEFAULTS = { width: 700, count: 12, padTop: 40, padBottom: 16, rowHeight: 22, columnWidth: 210 };

  function column(cities, valueOf, count, x, o) {
    return cities
      .slice()
      .sort((a, b) => valueOf(b) - valueOf(a) || a.city.localeCompare(b.city))
      .slice(0, count)
      .map(function (city, i) {
        return {
          key: city.city,
          label: city.city,
          value: valueOf(city),
          rank: i + 1,
          meta: city,
          x: x,
          y: o.padTop + i * o.rowHeight,
          w: o.columnWidth,
          h: o.rowHeight,
        };
      });
  }

  S.mismatchSpec = function (cities, options) {
    const o = Object.assign({}, DEFAULTS, options || {});
    const count = Math.min(o.count, cities.length);
    const left = column(cities, (c) => c.installations, count, 0, o);
    const right = column(cities, (c) => c.roi_pct, count, o.width - o.columnWidth, o);

    const rightByKey = new Map(right.map((r) => [r.key, r]));
    const gapLeft = o.columnWidth;
    const gapRight = o.width - o.columnWidth;

    const links = [];
    for (const row of left) {
      const match = rightByKey.get(row.key);
      if (!match) continue;
      const y1 = row.y + row.h / 2;
      const y2 = match.y + match.h / 2;
      const midpoint = (gapLeft + gapRight) / 2;
      links.push({
        key: row.key,
        y1: y1,
        y2: y2,
        d: "M" + gapLeft + "," + y1 +
           " C" + midpoint + "," + y1 + " " + midpoint + "," + y2 + " " + gapRight + "," + y2,
      });
    }

    return {
      left: left,
      right: right,
      links: links,
      width: o.width,
      height: o.padTop + Math.max(count, 1) * o.rowHeight + o.padBottom,
      columnWidth: o.columnWidth,
      padTop: o.padTop,
      padBottom: o.padBottom,
      plotLeft: 0,
      plotRight: o.width,
      ticks: [],
    };
  };

  function columnGroup(rows, spec, o, anchor, format, heading) {
    const group = S.svgEl("g", { class: "rank-column" });
    const x = anchor === "end" ? rows.length ? rows[0].x + spec.columnWidth : spec.columnWidth : 0;
    group.appendChild(S.svgEl("text", {
      class: "facet-title", x: x, y: 20, "text-anchor": anchor, text: heading,
    }));
    for (const row of rows) {
      group.appendChild(S.svgEl("circle", {
        cx: anchor === "end" ? row.x + row.w : row.x,
        cy: row.y + row.h / 2,
        r: 4,
        fill: o.colorOf(row),
      }));
      group.appendChild(S.svgEl("text", {
        class: "cat-label",
        x: anchor === "end" ? row.x + row.w - 12 : row.x + 12,
        y: row.y + row.h / 2 + 4,
        "text-anchor": anchor,
        text: row.rank + ". " + row.label + " · " + format(row.value),
      }));
    }
    return group;
  }

  S.drawMismatch = function (spec, options) {
    const o = options || {};
    const svg = S.svgRoot(spec, "The twelve largest solar deployments against the twelve best returns");

    const linkGroup = S.svgEl("g", { class: "links" });
    for (const link of spec.links) {
      linkGroup.appendChild(S.svgEl("path", {
        d: link.d, fill: "none", stroke: "var(--text-muted)", "stroke-width": 2,
      }));
    }
    svg.appendChild(linkGroup);

    svg.appendChild(columnGroup(spec.left, spec, o, "start", S.fmtCompact, "Most installations"));
    svg.appendChild(columnGroup(spec.right, spec, o, "end", (v) => S.fmt1(v) + "%", "Best return"));
    return svg;
  };

  S.register({
    id: "mismatch",
    page: "financial",
    title: "The mismatch",
    definition:
      "Left: the twelve cities with the most installations. Right: the twelve with " +
      "the highest ROI. A line is drawn only where a city appears in both columns.",
    wide: true,
    render: function (container, ctx) {
      const spec = S.mismatchSpec(ctx.cities, { width: 700, count: 12 });
      const overlap = spec.links.length;
      container.appendChild(S.el("div", { class: "hero" }, [
        S.el("p", { class: "hero-figure", text: String(ctx.payload.correlations.installations_vs_roi) }),
        S.el("p", { class: "hero-label",
          text: "correlation between where solar is installed and where it pays back. " +
                overlap + " of " + spec.left.length + " cities appear in both rankings." }),
      ]));
      container.appendChild(S.drawMismatch(spec, {
        colorOf: (row) => S.regionColorVar(row.meta.region, ctx.allRegions),
      }));
    },
    callout: (ctx) =>
      "Installed capacity is concentrated in China, India and Europe. Return is " +
      "concentrated in Phoenix, Dubai and Cairo. At r = " +
      ctx.payload.correlations.installations_vs_roi +
      ", knowing where panels went tells you almost nothing about where they pay back.",
    table: (ctx) => ({
      caption: "Deployment rank against return rank",
      columns: ["City", "Installations", "ROI %"],
      rows: ctx.cities
        .slice()
        .sort((a, b) => b.installations - a.installations)
        .slice(0, 12)
        .map((c) => [c.city, S.fmtInt(c.installations), S.fmt1(c.roi_pct)]),
    }),
  });
})(globalThis.SOLAR);
```

- [ ] **Step 4: Append the hero styles**

Add to `analysis/dashboard_assets/css/dashboard.css`:

```css
.hero { display: flex; align-items: baseline; gap: 18px; flex-wrap: wrap; margin-bottom: 20px; }
.hero-figure { margin: 0; font-size: 56px; font-weight: 700; letter-spacing: -0.04em; line-height: 1; }
.hero-label { margin: 0; max-width: 44ch; color: var(--text-secondary); font-size: 14px; }
.plot .rank-column .cat-label { fill: var(--text-primary); }
.plot .links path { opacity: 0.7; }
```

`.hero-figure` deliberately does not set `tabular-nums`: proportional figures are correct for a large standalone number.

- [ ] **Step 5: Register the asset — order matters**

In `analysis/build_dashboard.py`, `charts_mismatch.js` must load **before** `charts_bars.js` so the hero registers first and renders at the top of page 1. Final `ASSET_ORDER`:

```python
ASSET_ORDER = (
    "css/dashboard.css",
    "js/boot.js",
    "js/core.js",
    "js/rollup.js",
    "js/filters.js",
    "js/render.js",
    "js/charts_mismatch.js",
    "js/charts_bars.js",
    "js/charts_dots.js",
    "js/charts_scatter.js",
    "js/charts_map.js",
    "js/charts_matrix.js",
    "js/app.js",
)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `node --test tests/js/mismatch.test.mjs`
Expected: 11 pass, 0 fail

- [ ] **Step 7: Add the final structural assertions**

Append to `tests/test_build.py`:

```python
def test_all_thirteen_charts_are_registered(html):
    for chart_id in (
        "mismatch", "roi-by-city", "risk-by-region", "regional-roi-rank",
        "installations-vs-roi", "production-by-country", "installations-by-region",
        "production-consistency", "ghi-vs-production", "co2-by-country",
        "roi-vs-viability", "world-map", "region-country-city",
    ):
        assert f'id: "{chart_id}"' in html


def test_the_hero_module_loads_before_the_bar_module():
    assert ASSET_ORDER.index("js/charts_mismatch.js") < ASSET_ORDER.index("js/charts_bars.js")


def test_dark_theme_is_declared_under_both_scopes(html):
    assert "prefers-color-scheme: dark" in html
    assert ':root[data-theme="dark"]' in html
    assert ':root:not([data-theme="light"])' in html


def test_reduced_motion_is_respected(html):
    assert "prefers-reduced-motion" in html


def test_the_page_stays_under_the_size_budget(tmp_path):
    out = tmp_path / "dashboard.html"
    build(DATA, out)
    size_kb = out.stat().st_size / 1024
    assert size_kb < 400, f"dashboard is {size_kb:.0f} KB"
```

- [ ] **Step 8: Run everything and read the page properly**

Run: `python -m pytest tests/ -q` — all pass
Run: `node --test "tests/js/*.test.mjs"` — all pass
Run: `python -m analysis.build_dashboard`

Now go through the page against the dataviz anti-patterns, not just for crashes:

- No dual axes anywhere. No pie or donut. No area chart across categories.
- Gridlines are solid hairlines, one shade off the surface, never dashed.
- No bar touches its neighbour; every stacked segment carries its 2px gap.
- No label is clipped or overflowing its mark; nothing scrolls horizontally at 1280px, 900px and 375px wide.
- Filtering to one region does **not** recolour any other region.
- Every chart has a table twin except the matrix, which is a table.
- Tab through the whole page: focus is always visible and never trapped.
- Toggle to dark; re-check every chart. Bars, dots, links, graticule and hero figure must all still read against `#1a1a19`.
- Set the OS to dark with no explicit theme chosen — the page follows. Then click the toggle to light — the toggle wins.

Fix anything this pass finds before committing.

- [ ] **Step 9: Write the README**

Create `README.md`:

```markdown
# Solar Energy Worldwide — analysis and dashboard

An analysis of `solar_energy_worldwide.csv` (48 cities, 30 countries, 17 columns)
and a self-contained interactive dashboard built from it.

## What it says

- **Where solar is installed has almost nothing to do with where it pays back.**
  Installations and ROI correlate at 0.137. China, India and Europe hold the
  capacity; Phoenix, Dubai and Cairo hold the returns.
- **Four of the seventeen columns carry one column's information.** Estimated
  savings and CO₂ reduction are exact rescalings of annual production, and payback
  is that ratio rounded. Two more columns are constant across all 48 rows.
- **The supplied reference dashboard omits Dubai**, understating total CO₂ by 6.30 t,
  total installations by 850, and Asia's CO₂ by 6.30 t — and dropping the
  second-highest-ROI city from its ranking. `test_dubai_present_in_every_rollup`
  guards that defect in both the Python and JavaScript rollups.

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
python -m pytest tests/ -v   # pipeline, assembler, and the harness hooks
node --test tests/js/        # chart geometry, rollups, filter state
```

`tests/test_dashboard_js.py` runs the JavaScript suite from pytest, so
`python -m pytest` alone covers both languages.

## Layout

| Path | What it is |
|---|---|
| `analysis/metrics.py` | Derived measures: risk bands, regional rank, production consistency |
| `analysis/aggregate.py` | Region, country and city rollups |
| `analysis/build_data.py` | Validation, reconciliation, `output/data.json` |
| `analysis/build_dashboard.py` | Asset inlining, the self-containment gate, `output/dashboard.html` |
| `analysis/dashboard_assets/` | The shell, stylesheet and JavaScript modules that get inlined |
| `docs/superpowers/specs/` | The approved design |
| `docs/superpowers/plans/` | The two implementation plans |
| `docs/DECISIONS.md` | Choices made between real alternatives, with reasons |

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
```

- [ ] **Step 10: Record the decisions**

Append to `docs/DECISIONS.md`:

```markdown
## 2026-08-13 — Chart geometry lives in JavaScript, not Python

The spec puts chart modules under `analysis/charts/`. Cross-filtering changes which
rows exist, which changes bar count, scale domains and layout — not just
visibility — so a filtered view has to be laid out again from scratch. Rendering
statically in Python would mean either emitting all 32 filter combinations or
duplicating every layout rule in JavaScript. Chart geometry is therefore pure JS
in `analysis/dashboard_assets/js/`, unit-tested with `node --test`, and Python
assembles and gates the page. **Alternative rejected:** static SVG per filter
state — bloat, and the anti-pattern of two sources of truth for one layout.

## 2026-08-13 — The regional production scatter is faceted, not colour-coded

The spec asks for GHI against production "colored by region". Seven categorical
hues in a scatter is an all-pairs colour problem, and the validated palette clears
the all-pairs floors for three slots only; past that the dataviz rule is to facet
or fold to "Other", never to cycle. Seven small multiples on shared axes, each
with its region's hue over a muted context cloud, keeps region identity and
reads the pattern better than one overplotted panel. **Alternative rejected:**
seven hues in one cloud — fails the CVD floors with no secondary encoding available.

## 2026-08-13 — Payback risk uses the status palette, not categorical slots

Low / Medium / High is severity, not identity, so it takes the reserved status
colours (good / warning / critical) rather than three categorical slots. Two of
those are under 3:1 on the light surface by design, so every segment ships with a
label and the chart has a table twin. **Alternative rejected:** an ordinal
one-hue ramp — legal, but it reads as magnitude rather than as risk state.

## 2026-08-13 — The world map has no basemap

Coastline geometry is tens of kilobytes and cannot be fetched under the
self-containment rule. A labelled 30° graticule with the equator and both tropics
gives the projection honestly at no cost. **Alternative rejected:** an inlined
simplified coastline — cost without analytical return.

## 2026-08-13 — The installations axis is square-rooted

Installations span 150 to 609,000. On a linear axis 44 of 48 cities collapse
against the left edge and the r = 0.137 finding is invisible. The axis is
square-rooted, the axis title says so, and ticks are printed as real counts.
**Alternative rejected:** log scale — undefined shape near the small values here
and harder to read back to counts.
```

- [ ] **Step 11: Update the intent block in `docs/STATE.md`**

Edit **only** between `<!-- INTENT:BEGIN -->` and `<!-- INTENT:END -->`. The facts block above it is script-owned:

```markdown
- Decisions: chart geometry is pure JS unit-tested with `node --test`, Python
  assembles and gates self-containment; the regional production scatter is
  faceted rather than seven-hue coloured; payback risk uses status colours.
  Full reasoning in docs/DECISIONS.md.
- Next step: Plan A and Plan B are complete. `python -m analysis.build_data`
  then `python -m analysis.build_dashboard` reproduces both outputs from the CSV.
```

- [ ] **Step 12: Final verification, then commit**

Run these and read the output rather than assuming it:

```bash
python -m pytest tests/ -q
node --test tests/js/
python -m analysis.build_data
python -m analysis.build_dashboard
```

Expected: every test passes; `build_data` prints `48 cities, 30 countries, 7 regions, 208.35 t CO2, 2328540 installations`; `build_dashboard` prints a size and `self-contained`.

Then commit:

```bash
git add analysis/dashboard_assets analysis/build_dashboard.py tests README.md docs/DECISIONS.md
git -c user.name="chinm" -c user.email="mishraswagat2804@gmail.com" commit -m "feat: add the mismatch hero, README, and decision records"
```

---

## Self-review

**Spec coverage.**

| Spec requirement | Task |
|---|---|
| Single self-contained HTML file | 1 (`assert_self_contained`, gated before write) |
| Hand-built inline SVG, no library | 5–8, 10 |
| Page 1 — ROI by city | 5 |
| Page 1 — Payback risk by region, stacked | 5 |
| Page 1 — Regional ROI ranking, dot plot | 6 |
| Page 1 — Installations vs ROI with the r = 0.137 callout | 7 |
| Page 2 — GHI vs production, by region | 7 (faceted; deviation recorded in Task 10) |
| Page 2 — Average production by country | 5 |
| Page 2 — Installations by region, bars not area | 5 |
| Page 2 — Production consistency with explicit n/a | 6 |
| Page 3 — CO₂ by country | 5 |
| Page 3 — ROI vs viability | 7 |
| Page 3 — Region → country → city matrix, correct decimals | 9 |
| Page 3 — World map, bubbles by installations | 8 |
| Page 3 — Data caveats panel | 1 (shell) + 4 (rendered from `payload.caveats`) |
| Cuts: avg price by region, investment efficiency, CO₂ vs production | Never built — no task creates them |
| Region and risk chips cross-filter every chart | 4 |
| Clicking a region bar filters to that region | 5, 6, 7, 8 (`ctx.isolate`) |
| One reset control | 4 |
| Keyboard-reachable filters, no hover-only information | 4, 5, 6, 9 (focus handlers, table twins) |
| Colorblind-safe seven-region palette | Global Constraints (validated), 2 (`regionColorVar`) |
| Theme-aware, both scopes | 1 (CSS), 10 (asserted) |
| Fail loud on any external reference | 1 |
| `test_build.py`: no external URL, data inline, 48 cities | 1, 10 |
| Derived measures stated on the dashboard | Every chart's `definition` field, 5–10 |
| Never modify the CSV; never recode Region | Global Constraints; no task writes to either |

**Placeholder scan.** No "TBD", no "add error handling", no "similar to Task N", no test described without its code. Every code step carries the code it needs.

**Type consistency.** `barSpec`/`stackSpec`/`dotSpec`/`scatterSpec`/`mapSpec`/`mismatchSpec` all return an object carrying `width`, `height`, `padTop`, `padBottom`, `plotLeft`, `plotRight` and `ticks`, because `svgRoot` and `drawAxisX` consume exactly those; `mapSpec` and `mismatchSpec` supply empty `ticks` for that reason. `scatterSpec` carries both `ticks` and `xTicks` — `drawAxisX` reads `ticks`, `drawAxisY` reads `yTicks`. Chart records are `{id, page, title, definition, wide?, render?, callout?, table?}` in every registration and in `renderCharts`. `ctx` is built once in `buildContext` and carries `payload, state, cities, regions, countries, totals, allRegions, allBands`, with `isolate` attached in `render`. `S.BANDS` is defined once in `filters.js` and reused by `stackSpec` callers and `riskCountsOf`. `regionColorVar(region, allRegions)` is always called with `ctx.allRegions`, never with a filtered list. `attachTip(node, modelFn)` is stubbed in Task 5 and replaced in Task 9 — every earlier caller keeps working because the signature does not change.

**Known ordering constraints.** `app.js` is last in `ASSET_ORDER`; `charts_mismatch.js` precedes `charts_bars.js`; `render.js` precedes every chart module. Task 10 states the final tuple in full so no task has to guess.
