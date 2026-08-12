# Decisions

Append-only. Newest last. One entry per real choice between alternatives.

## 2026-08-12 — Context harness architecture

Chose script-written facts plus model-written intent, injected once per session
at `SessionStart`. Rejected per-prompt `UserPromptSubmit` injection: it blocks
every turn and re-spends tokens each time, which defeats the purpose.

Chose mtime comparison over transcript parsing for the checkpoint gate —
deterministic and independent of transcript format.
