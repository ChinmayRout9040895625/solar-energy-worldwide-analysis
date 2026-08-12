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
