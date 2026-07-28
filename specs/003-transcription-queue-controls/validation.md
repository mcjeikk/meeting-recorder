# Validation Report: Transcription Queue Controls

**Feature**: `003-transcription-queue-controls`  
**Date**: 2026-07-27  
**Scope**: Evidence grounding before plan/tasks (no performance claims beyond cancel-stops-work)

## What was validated

| Area | Method |
|------|--------|
| Current TX UI | Code read of `app/ui/main_window.py` banner: progress, Open, Retry, Ver log; ✕ hides banner only |
| Cancel API | Grep/read `jobs.py` / `worker.py` — no `cancel`; worker `shutdown` does not kill child |
| Language | `AppConfig.transcription_language` + `enqueue(..., language)` + CLI `--language`; **no UI combo** |
| Clear failed | No `delete`/`clear` on `JobStore`; queue JSON accumulates |
| Desktop patterns | Common single-user queue UX: Cancel on active item, language before enqueue, clear failed — no full history required for MVP |
| Constitution | Cancel must not touch recording; sibling subprocess stays; durable queue outside OneDrive |

## Assumptions locked for plan

1. Add explicit `cancelled` job status (distinct from `error`).
2. Language MVP options: `es` / `en` / `auto` only.
3. Clear failed = remove `error` + `cancelled` queue files; leave `pending`/`extracting`/`running`/`done`.
4. Cancel running job = best-effort terminate of owned sibling PID + mark cancelled; Recording Always Wins unchanged.
5. No full queue history panel in this feature.

## Residual risks

- Cross-instance cancel (another Recorder holds the worker lock) may only flip durable status until the owner notices — acceptable for single-user MVP.
- Abrupt kill of Transcriptor may leave partial output files; success remains exit code + artifacts (partial ≠ done).
- Auto language quality depends on sibling ASR; product already supports `auto` in config.

## Recommendation

**GO** — proceed to plan + tasks + tightly scoped implement.
