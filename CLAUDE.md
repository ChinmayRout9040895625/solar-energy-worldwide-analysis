# Solar Energy Worldwide Analysis

Analysis of `solar_energy_worldwide.csv` (48 cities, 17 columns) producing
viability scoring, ROI comparison, regional breakdowns, and a dashboard.

## Response contract

- Answer first. No preamble, no restating the question, no "great question".
- Findings as tight bullets or a small table. Prose only when reasoning matters.
- Code without narration. Explain a line only if it is genuinely non-obvious.
- State uncertainty in one clause, not a paragraph. Never pad to sound thorough.
- Report what happened, not what should have. If a test failed, show the output.

Verbosity follows `verbosity` in `.claude/context.config.json`: `lean` (default)
= minimum that fully answers; `normal` = add brief rationale; `explain` = walk
through the reasoning. Read the config if unsure which is active.

## Model routing

Main thread is Opus 5 at high effort: planning, architecture, debugging,
interpreting ambiguous results, deciding approach.

Delegate to Sonnet workers when the task is mechanical, fully specified, and
verifiable without judgment:

| Agent | Delegate for |
|---|---|
| `data-profiler` | describes, null/outlier scans, group-bys, correlations |
| `chart-builder` | building one chart to an explicit spec |
| `doc-writer` | README sections, docstrings, memory notes |
| `verifier` | running tests or scripts and reporting pass/fail |

Do **not** delegate: choosing an approach, interpreting an ambiguous result,
debugging, or anything where you would have to guess what the user wants.

**Anti-rule:** never delegate work smaller than the spawn cost. Single-file
reads, one-line edits, and quick greps stay on the main thread. Set
`delegation.enabled` to `false` to suspend delegation.

## Context system

- `docs/STATE.md` — auto-injected at session start. The facts half is
  script-owned and git-ignored; never hand-edit it. The intent half is yours,
  and the Stop gate will block until you update it once you have done work
  (files under `work_dirs`, or matching `work_globs` at the repo root).
- `docs/memory/*.md` — deeper notes; the injected block lists paths and one-line
  descriptions only, so read a note when the task touches it, not preemptively.
  Machine-written pre-compact snapshots go to `docs/memory/precompact/`, which is
  deliberately outside that index.
- `docs/DECISIONS.md` — append-only. Record a decision when you choose between
  real alternatives, with the reason.
- `docs/token_log.jsonl` — what each injection cost, if the harness feels pricey.

## Project layout

- `analysis/` — analysis scripts (`analysis/charts/` for plotting scripts)
- `output/` — generated charts and the dashboard
- `.claude/hooks/` — harness hooks, stdlib-only, must fail open; `tests/` — their
  pytest suite. Run tests with `python -m pytest tests/ -v`.
