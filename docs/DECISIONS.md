# Decisions

Append-only. Newest last. One entry per real choice between alternatives.

## 2026-08-12 — Context harness architecture

Chose script-written facts plus model-written intent, injected once per session
at `SessionStart`. Rejected per-prompt `UserPromptSubmit` injection: it blocks
every turn and re-spends tokens each time, which defeats the purpose.

Chose mtime comparison over transcript parsing for the checkpoint gate —
deterministic and independent of transcript format.

## 2026-08-13 — Closing the self-refresh loop

The loop never actually closed. `checkpoint_gate.py` watched a hardcoded
`("analysis", "output", "docs/memory")`, none of which existed with content, so
`needs_checkpoint` returned `False` unconditionally and the intent half of
`docs/STATE.md` sat at its placeholder through 15 commits of real work.

Chose config-driven `work_dirs` plus root-level `work_globs` over widening the
hardcoded tuple: the config is meant to be the single source of truth, and
watching the repo root non-recursively means the gate works from the first
commit rather than only after `analysis/` exists.

Dropped `docs/memory` from the watch list and moved pre-compact notes to
`docs/memory/precompact/`. Compaction wrote into a watched directory, so the
gate could fire for a compaction in which the user did no work; the subdirectory
also keeps machine notes out of the non-recursive memory index.

`inject_context.py` now skips the facts rewrite when `source` is `resume` or
`compact`. Rewriting `STATE.md` mid-session bumped its mtime to now, which
retroactively made every work file written earlier in the session look older
than the state file and erased the gate's evidence. The block is still emitted
on those sources — the model needs its context back after a compaction.

Stopped tracking `docs/STATE.md` in git. It is machine-regenerated, exactly like
`docs/token_log.jsonl`. This also removes the permanent working-tree noise and
the off-by-one in the injected uncommitted-file count, which was collected
before the harness dirtied the file it was counting.

Also: ordered marker validation in `state.py` (misordered markers passed the
presence check and duplicated the intent block on every write), a genuine
no-op kill switch, and `preserve_compact` made switchable like the other hooks.

## 2026-08-13 — Chart geometry lives in JavaScript, not Python

The dashboard spec puts chart modules under `analysis/charts/`. Cross-filtering
changes which rows exist, which changes bar count, scale domains and the whole
layout — not just visibility — so a filtered view has to be laid out again from
scratch. Rendering statically in Python would mean either emitting all 32 filter
combinations or duplicating every layout rule in JavaScript anyway.

Chose pure-JS geometry in `analysis/dashboard_assets/js/`, unit-tested with
`node --test`, with Python assembling and gating the page. Rejected static SVG
per filter state: bloat, and two sources of truth for one layout.

The divergence risk this creates is real, so `rollup.js` is checked field for
field against the Python-emitted `regions` and `countries` arrays. Verified
first that summing the display-rounded city values reproduces every group total
with zero drift, so those comparisons are exact rather than tolerant.

## 2026-08-13 — The regional production scatter is faceted, not colour-coded

The spec asks for GHI against production "colored by region". Seven categorical
hues in one scatter is an all-pairs colour problem, and the validated palette
clears the all-pairs floors for three slots only; past that the dataviz rule is
to facet or fold to "Other", never to cycle hues.

Chose seven small multiples on shared axes, each in its region's hue over a muted
context cloud of every city in view. Rejected seven hues in one cloud: it fails
the CVD floors, and no secondary encoding rescues an overplotted scatter.

## 2026-08-13 — Payback risk uses the status palette, not categorical slots

Low / Medium / High is severity, not identity, so it takes the reserved status
colours rather than three categorical slots. Two of those sit under 3:1 on the
light surface by design, so every segment ships with a label and the chart has a
table twin. Rejected an ordinal one-hue ramp: legal, but it reads as magnitude
rather than as risk state.

## 2026-08-13 — The world map has no basemap

Coastline geometry is tens of kilobytes and cannot be fetched under the
self-containment rule anyway. Chose a labelled 30° graticule with the equator and
both tropics: it states what the projection is, at no cost. Rejected an inlined
simplified coastline — weight without analytical return.

## 2026-08-13 — The installations axis is square-rooted

Installations span 150 to 609,000. On a linear axis 44 of the 48 cities collapse
against the left edge and the r = 0.137 finding becomes invisible. Chose a
square-root axis with the transformation named in the axis title and ticks
printed back as real counts. Rejected a log scale: harder to read back to counts
for no gain at this range.

## 2026-08-13 — The chart registry lives in boot.js

Found while building the bar charts: chart modules call `S.register` at load
time, but the registry was defined in `app.js`, which is deliberately last in
`ASSET_ORDER` so that `mount` runs after every chart exists. The built page would
have thrown on the first chart module. Moved the registry to `boot.js`, which
owns the namespace and loads first.

Added `tests/js/page.test.mjs` in the same change: it reads `ASSET_ORDER` out of
`build_dashboard.py`, loads the modules in exactly that order against the DOM
shim, and mounts them. Per-module tests could not have caught this, because each
one loads only what it needs.

## 2026-08-13 — Power BI added as a second medium, in TMSL + PBIR-Legacy

The approved spec chose a self-contained HTML file and explicitly listed
"Reproducing Power BI as a file format" as out of scope. That was reversed on
request: the deliverable was expected to be a Power BI dashboard.

Chose PBIP with a TMSL `model.bim` and a PBIR-Legacy `report.json`. The newer
TMDL and PBIR folder formats diff far better and are publicly schema'd, but both
are preview features gated behind Desktop flags, and the installed build is
2.139 (Dec 2024) — roughly twenty months older than the schemas Microsoft now
documents. TMSL and PBIR-Legacy are read natively by every Desktop since 2019
and are still plain JSON, so the generator can validate everything it emits.
Rejected: `.pbix`, which wraps a compiled Analysis Services model and cannot be
authored by hand.

Chose to embed all 48 rows in the model as a literal M `#table`. A file path in
a Power BI query is absolute, so a generated project pointing at this machine's
CSV would break as soon as it moved. Embedding costs ~20 KB and makes the
project open anywhere — the same self-containment rule the HTML page follows.
Rejected `Csv.Document(File.Contents(...))` for that reason.

Limitation stated rather than hidden: nothing executes DAX at build time, so the
measures are translations of `analysis/metrics.py`, not verified computations.
The build prints the figures each card should show, and a test asserts that
every measure a visual binds to actually exists in the model — which is the
failure this generator is most likely to produce.

## 2026-08-13 — Report switched from PBIR-Legacy to PBIR after a blank canvas

The first Power BI attempt emitted PBIR-Legacy (`report.json`), chosen to avoid
requiring a preview toggle on a Dec-2024 Desktop. It opened to a completely
blank canvas.

Root cause, found in the docs already consulted for the build: `report.json`
"doesn't support external editing". Desktop reads the project, takes its name —
hence a correct window title — and discards a layout it did not author. The
missing `query`/`dataTransforms` keys were a symptom of that, not the cause;
patching them would have chased the wrong thing.

Switched to PBIR (`definition/` folder), which Microsoft explicitly documents as
"a publicly documented format that supports modifications from non-Power BI
applications", with a JSON schema per file and blocking errors that name the
offending file. It costs a preview toggle, which is now stated in the README and
in the build output. Two schema mistakes surfaced immediately once the real
schemas were read: `displayOption` is a string enum (`FitToPage`), not an
integer, and `layoutOptimization` is `"None"`, not `0`.

Lesson recorded because it generalises: "the older format is safer" was an
assumption about compatibility that ignored a documented statement about
supportability. The format designed for the job beat the format that merely
looked more established.

## 2026-08-13 — .pbit attempt abandoned; findings kept, code removed

Third Power BI approach: generate a .pbit template, chosen because it needs no
preview toggle and refreshes on open. Power BI Desktop rejected it with "This
file is corrupted or was created by an unrecognized version of Power BI
Desktop" — a container-level rejection, before any JSON was read.

The generator reached exact key parity with a real .pbix (part names, UTF-16LE
without BOM, Content_Types overrides, and layout keys at all three levels) and
still failed, so something structural in the OPC package is missing that cannot
be inferred from a .pbix — a .pbix has DataModel where a .pbit has
DataModelSchema, and no .pbit was available to compare against. Deleted the code
rather than keep something that does not open.

Worth keeping from it, because it explains the FIRST failure too: in the legacy
Layout each visualContainer carries three sibling documents, not one —
`config`, plus **`query`** (a SemanticQueryDataShapeCommand with a Binding) and
**`dataTransforms`** (selects + projectionOrdering). A container with only
`config` renders as nothing. Two shapes that look alike and are not: the query's
Select uses `SourceRef.Source` (the From alias) while dataTransforms' expr uses
`SourceRef.Entity` (the table name). Sections also need an integer `id` and an
integer `displayOption`.

Rule taken from three failures: do not author a Power BI report container from
inference. Either use PBIR, which Microsoft documents for external authoring, or
start from a real file of the exact same kind and modify it.

## 2026-08-13 — The model half is proven; the report half is not

Independently confirmed: `msmdsrv.exe` loaded the generated model at 542 MB and
`Cities` appears in the Data pane, so model.bim, the embedded M table and the
measures are all accepted by Desktop. Desktop also raises "Some of the tables
have incomplete or no data" — a generated project has no cache.abf, so any
route needs one Refresh before numbers appear.

## 2026-08-13 — Power BI report solved: patch a Desktop-exported skeleton

Working. The route that succeeded is not "generate a .pbit" but "take one
Desktop exported and replace a single part".

Two root causes, found by copying instead of inferring:

1. **SecurityBindings binds to the package contents.** It is a DPAPI blob, and
   rewriting any part invalidates it — Desktop then reports "This file is
   corrupted or was created by an unrecognized version", which reads like a
   format-version problem and is not. The fix is to DROP the part and its
   Content_Types override, which is what every tool that recompiles a pbix/pbit
   does. This was invisible from the .pbix reference because that file was never
   modified.
2. **Each visualContainer needs three sibling documents.** `config` alone
   renders nothing; `query` (a SemanticQueryDataShapeCommand with a Binding)
   and `dataTransforms` (selects + projectionOrdering) are required too. This
   was the real cause of the very first blank report, misattributed at the time
   to PBIR-Legacy being unreadable.

`analysis/build_pbit.py` therefore copies every part of the skeleton byte for
byte, drops SecurityBindings, and swaps Report/Layout. The skeleton carries the
semantic model Desktop already accepted, so the model is never rebuilt either.
Re-export the skeleton when the model changes.

Verified on screen: Cities 48, CO2 208.35 t, Installations 2M, Mean ROI 10.86%
— all matching output/data.json — with both slicers populated and the ROI,
risk, regional-ROI and scatter visuals drawing real data.

Cost of the lesson: three failed attempts, all of which inferred a proprietary
format from documentation or an unrelated file. The one that worked started
from a real artifact of the exact same kind.

## 2026-08-13 — Power BI theme ships beside the template, not inside it

Wrote a custom theme (`analysis/dashboard_assets/powerbi_theme.json`) reusing the
same validated colourblind-safe palette as the HTML dashboard, so the two
deliverables read as one system.

Embedding it in the .pbit failed twice — once as a RegisteredResources package
with `themeCollection.customTheme`, once as SharedResources/BaseThemes with
`themeCollection.baseTheme`, the latter copied verbatim from a real .pbix that
ships a theme. Both loaded without error and without effect. Stopped there
rather than guess a third shape, which is the exact mistake this project already
made three times over the container format.

The theme is written to `output/powerbi/SolarEditorial.json` and imported in
Desktop (View > Themes > Browse for themes). Once imported it is captured by the
next skeleton export, after which every build carries it — the same mechanism
that already supplies the model.

## 2026-08-13 — No table visual in the generated report

`tableEx` renders its header and no rows from a generated layout. Three
attempts: plain binding, then a Window data reduction, then `Subtotal: 1` plus
`queryMetadata` and `visualElements` — the last two lifted verbatim from a
working tableEx in a real .pbix. Charts, cards, slicers and scatters all render
from the same code path, so the defect is specific to the table binding.

Shipped charts in its place: a blank box is worse than a different working
visual. If the row-level detail is wanted, insert a Table visual in Desktop and
drag Region, Country and City onto it — about ten seconds, and it then survives
in the skeleton.

## 2026-08-13 — Styling applied per visual, not via a theme

The theme JSON could not be made to take effect from inside the .pbit (two
shapes tried, both loaded silently doing nothing). Styling is therefore written
onto each visual through the `objects` / `vcObjects` channel in its config —
the same expr/Literal mechanism the visual titles already rendered through, so
this was demonstrated rather than assumed before being relied on.

What that buys over a theme: it is generated, version-controlled and
reproducible. `python -m analysis.build_pbit` reproduces the exact look with no
manual import, and no step that can be forgotten.

Applied: white card surfaces on a warm #F4F3EF plane, #E1E0D9 hairline borders
at 8px radius, no drop shadows, muted 10px left-aligned titles, 30px ink KPI
values with muted captions, and mark colours from the HTML dashboard's
validated palette — blue for ROI, critical red for payback risk, aqua and green
for regional and sustainability measures.

`analysis/dashboard_assets/powerbi_theme.json` is kept and still shipped to
output/. It is now optional: import it only to make hand-added visuals match.
