# Implementation Plan: Model-Load Reuse (Phase 2)

**Branch**: `005-model-load-reuse` | **Date**: 2026-07-28 | **Spec**: [spec.md](./spec.md)

## Summary

Refine the constitution-compliant approach for reusing ASR model load across consecutive Transcriptor jobs **without** fusing venvs or weakening Recording Always Wins. **This pass: documentation + explicit deferral of code.** A half-broken daemon or unused keep-alive flag would not ship value; multi-monitor / preview / mute take priority.

## Technical Context

**Language/Version**: Python 3.11.9 (separate Recorder + Transcriptor venvs)

**Primary Dependencies**: Existing subprocess queue worker; Transcriptor `faster-whisper` / CTranslate2 (sibling only)

**Storage**: Durable JSON queue under `%LOCALAPPDATA%\MeetingRecorder\transcripts\`

**Testing**: When implemented later — cold vs warm wall-clock on same short sample + same preset; Recording Always Wins suspend check

**Target Platform**: Windows desktop

**Project Type**: desktop-app + sibling CLI

**Performance Goals**: Second same-preset job reduces model-init overhead vs cold start (when code exists)

**Constraints**: Constitution I–V; no fused venv; no torch in Recorder; no Scheduled Task mega-worker

**Scale/Scope**: Docs this pass; future optional sibling warm worker

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Recording Always Wins | PASS (design) | Future warm child still subject to refuse-spawn / suspend |
| II. Privacy Is Local | PASS | No cloud |
| III. Sibling Subprocess | PASS | Reuse only inside Transcriptor process/env |
| IV. Robust paths/processes | PASS | List-args; log file not pipe |
| V. Simplicity | PASS | Deferring mega-daemon for single user |

**Gate**: PASS for docs; **FAIL if** this pass tried to ship a partial daemon without Recorder integration tests.

## Project Structure

```text
specs/005-model-load-reuse/
├── spec.md
├── validation.md
├── plan.md
├── research.md
├── deferral.md          # decision for this pass
├── quickstart.md        # measurement when implemented
└── tasks.md
```

No application code changes in this pass.

## Phase 0 research → see research.md

## Implementation Approach

### This pass (ship)

1. Spec + validation + plan + research + deferral note.
2. Cross-link from 002 Phase 2 section to 005.
3. Commit docs only.

### Future pass (not started)

1. Optional Transcriptor long-lived worker holding `WhisperModel` keyed by (model, device, compute_type).
2. Minimal IPC (named pipe or localhost) with job payload = existing CLI args semantics.
3. Recorder worker: prefer warm endpoint if reachable; else cold `transcribe.py` (unchanged).
4. Recording Always Wins: do not start warm jobs while recording; `psutil.suspend` on warm child same as today.
5. Measure cold vs warm; document in quickstart.

### Rejected now

- Fused venv / import ASR into Recorder.
- Opt-in `--keep-alive` on CLI with zero Recorder callers (dead surface).
- Windows Scheduled Task always-on worker.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | Full daemon deferred; no violation introduced |
