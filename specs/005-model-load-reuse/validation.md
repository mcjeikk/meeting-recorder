# Validation Report: Model-Load Reuse (Phase 2)

**Feature**: `005-model-load-reuse`  
**Date**: 2026-07-28  
**Scope**: Evidence grounding before plan; decide ship vs defer for this pass

## What was validated

| Area | Method |
|------|--------|
| Constitution III/I/V | `.specify/memory/constitution.md` + CLAUDE.md (sibling CLI, no fused venv, Recording Always Wins, no scheduled mega-worker) |
| Current integration | Recorder `transcription/worker.py` + `integration.build_command` — one subprocess per job; stdout to log file |
| 002 Phase 2 prior art | `specs/002-transcription-speed-presets/plan.md` options A/B/C; research E4 (CTranslate2 load-once) |
| Transcriptor shape | One-shot `transcribe.py`; no long-lived worker today; separate `.venv` |
| Keep-alive slice risk | Wiring Recorder ↔ warm protocol needs durable queue + suspend/resume + crash recovery — not a one-pass MVP |

## Assumptions locked

1. **Full sibling daemon** (socket/stdin protocol + model hold) is the only meaningful reuse path; in-process CLI cache does not help one-file-per-job.
2. **Half-wired keep-alive** unused by Recorder adds maintenance with no user value → reject for this pass.
3. **Defer implement** with refined plan + note; unlock multi-monitor / preview / mute.

## Residual risks

- Future daemon must not fuse venvs or import torch into Recorder.
- Measurement without daemon is N/A; document steps for later.

## Recommendation

**DEFER CODE** — refresh plan artifacts only; proceed to 006+.
