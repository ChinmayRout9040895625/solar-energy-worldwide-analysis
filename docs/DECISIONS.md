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
