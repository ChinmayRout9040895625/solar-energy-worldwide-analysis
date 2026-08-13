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
