# Dynamic Context Management Harness — Design

**Date:** 2026-08-12
**Project:** solar_energy_worldwide_analysis
**Status:** Approved design, ready for implementation planning

## Purpose

Build a project-local, token-optimized context management system for this workspace. The system keeps a self-refreshing context file that is auto-injected at session start, routes high-reasoning work to Opus 5 and mechanical work to Sonnet subagents, and enforces terse response output. It is built as a self-contained folder that can be copied to future projects.

The system is infrastructure. The project deliverable it supports is a Python analysis of `solar_energy_worldwide.csv` (48 cities, 17 columns) plus an interactive dashboard covering viability scoring, ROI comparison, and regional breakdowns.

## Grounding

Design follows four techniques from Anthropic's context engineering guidance:

- **Just-in-time retrieval** — keep lightweight identifiers in context, load payloads at runtime.
- **Structured note-taking** — persist progress notes outside the context window, re-read on demand.
- **Compaction** — high-fidelity summarize-and-restart near the window limit.
- **Sub-agent architectures** — isolated contexts explore widely and return condensed digests.

Confirmed harness mechanics: `SessionStart` and `UserPromptSubmit` both support `hookSpecificOutput.additionalContext` for silent injection. `UserPromptSubmit` blocks model processing until it returns (30s default timeout), which is why this design injects once per session rather than per prompt.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Scope | Project-local under `./.claude/` | Keeps global config clean; portable by copying the folder |
| State authorship | Script writes facts, Claude writes intent | Facts are deterministic and free; intent needs judgment |
| Injection frequency | Once per session (`SessionStart`) | Per-prompt injection would fight the token-optimization goal |
| Model routing | Named Sonnet workers, Opus decides | Predictable and debuggable; no hook can switch the main model |
| Control surface | Single `context.config.json` | Behavior changes without hook edits |
| Response style | Terse contract in `CLAUDE.md` | Travels with the folder; verbosity tunable via config |
| Reasoning effort | `effortLevel: high` in project settings | Global is currently `low`, which undercuts Opus-as-master; setting it project-locally keeps scope contained |

## Architecture

### File layout

```
CLAUDE.md                      # response contract + routing policy (~40 lines, always loaded)
.claude/
  settings.json                # hooks, model, effortLevel, permissions
  context.config.json          # every knob, single source of truth
  hooks/
    inject_context.py          # SessionStart → builds + emits state block
    checkpoint_gate.py         # Stop → ensures intent got recorded
    preserve_compact.py        # PreCompact → protects decisions
  agents/
    data-profiler.md           # model: sonnet
    chart-builder.md           # model: sonnet
    doc-writer.md              # model: sonnet
    verifier.md                # model: sonnet
docs/
  STATE.md                     # living state: facts (script-written) + intent (Claude-written)
  DECISIONS.md                 # append-only, why-choices
  memory/                      # deeper notes, loaded just-in-time by path only
  token_log.jsonl              # what each injection cost
```

### Two context layers

**Always-loaded:** `CLAUDE.md` plus the injected state block. Combined ceiling 800 tokens.

**On-demand:** everything in `docs/memory/`. The state block lists these as paths with one-line descriptions only. Opus reads a note only when the task touches it.

## The refresh loop

### SessionStart — `inject_context.py`

Pure Python, no model call, must complete in under 1 second.

1. Read `context.config.json` for enabled blocks and token budgets.
2. Compute the facts half: CSV schema and row count, files in `analysis/` and `output/`, git status if the project is a repo, which memory notes exist.
3. Read the intent half verbatim from `docs/STATE.md`.
4. Rewrite the facts half of `STATE.md` so the on-disk file stays true.
5. Emit `{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "<block>"}}`, truncated to budget.
6. Append the block's token estimate to `token_log.jsonl`.

### Stop — `checkpoint_gate.py`

A hook cannot make the model generate text directly. The gate inspects the transcript; if files changed during the session but `STATE.md`'s intent section was not touched, it returns:

```json
{"decision": "block",
 "reason": "Append this session's decisions and next step to docs/STATE.md intent section, then stop."}
```

This hands control back to the model to perform the write. Guarded by `stop_hook_active` so it fires at most once per session and cannot loop.

### PreCompact — `preserve_compact.py`

Writes the current intent section and open threads to `docs/memory/pre-compact-<timestamp>.md`, and instructs the summarizer to preserve the state block verbatim.

### Cost profile

One injection per session plus one short model write at session end. Not per-prompt.

## Model routing

Main thread is Opus 5 at `effortLevel: high`: planning, debugging, architecture, brainstorming — anything where being wrong is expensive.

| Agent | Job | Returns |
|---|---|---|
| `data-profiler` | pandas describes, null/outlier scans, group-bys | ≤300-token digest |
| `chart-builder` | writes one chart script to spec, runs it, confirms output exists | file path + confirmation |
| `doc-writer` | README sections, docstrings, memory-note formatting | the text only |
| `verifier` | runs tests/scripts, reports pass/fail with failing output | verdict + failure excerpt |

Each agent declares `model: sonnet`, a narrow tool allowlist, and an explicit instruction to return a digest rather than a transcript. The digest requirement is where the token saving originates.

**Routing policy** (~8 lines in `CLAUDE.md`): delegate when the task is mechanical, well-specified, and its output is verifiable without judgment. Keep work on Opus when it involves choosing an approach, interpreting an ambiguous result, or debugging. Anti-rule: never delegate work smaller than the agent spawn cost — single-line edits stay on the main thread.

## Configuration

`.claude/context.config.json`:

```json
{
  "verbosity": "lean",
  "token_budget": { "total": 800, "facts": 400, "intent": 300, "memory_index": 100 },
  "blocks": { "data_schema": true, "artifacts": true, "git": true,
              "intent": true, "memory_index": true },
  "delegation": { "enabled": true, "min_task_size": "multi-step" },
  "checkpoint_gate": true,
  "token_logging": true
}
```

All hooks read this at runtime. Setting every entry in `blocks` to false disables the system without editing or uninstalling hooks.

## Response contract

Lives in `CLAUDE.md`. Rules: answer first; no preamble or restating the question; findings as tight bullets; code without narration; state uncertainty in one clause rather than a paragraph.

`verbosity` has three settings — `lean`, `normal`, `explain` — which the contract references by name, so output shape can be loosened for a debugging session without editing prose.

## Failure behavior

**Hooks fail open, always.** Every hook wraps its body in try/except and on any error prints nothing and exits 0. A broken hook degrades to "no injected context," never to a blocked session.

- `inject_context.py` hard-caps its own output so an oversized file cannot blow the context window.
- A missing or malformed `STATE.md` is regenerated from template rather than treated as an error.
- A missing `context.config.json` falls back to documented defaults matching the JSON above.

## Testing

Unit tests for `inject_context.py` against fixture directories, each asserting valid JSON on stdout and exit code 0:

- empty project
- populated project
- malformed `STATE.md`
- missing `context.config.json`
- oversized memory index (budget truncation)

`checkpoint_gate.py` gets an explicit test asserting it never blocks twice when `stop_hook_active` is set.

Live verification with `claude --debug` to confirm the injected block actually lands in context.

## Open risk

On a 48-row dataset, the ~800-token per-session injection may cost more than it saves. `token_log.jsonl` exists specifically so this is measurable rather than assumed. The system's value is expected to come from workflow discipline and portability rather than raw token savings on this particular dataset. If the log shows the overhead is not earning its place, the config kill switch is the exit.

## Out of scope

- Global (`~/.claude/`) configuration changes — `effortLevel` is set in project settings instead
- `UserPromptSubmit` per-prompt injection
- MCP server additions
- The solar analysis and dashboard themselves — separate spec, built using this harness
