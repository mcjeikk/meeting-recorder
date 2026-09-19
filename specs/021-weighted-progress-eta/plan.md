# Implementation Plan: Progress that means something, and a time estimate

**Branch**: `021-weighted-progress-eta` | **Date**: 2026-09-18 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/021-weighted-progress-eta/spec.md`

## Summary

Spec 020 made the percentage point at the right file; it still only measures the transcription phase, so it races to 90% and stalls for hours in speaker identification. Replace it with a time-based model: audio duration (exact, from the 16 kHz work WAV size) × a speed factor per configuration (measured: 1.08× with more CPU, 1.45× keeping the PC usable), giving both a weighted percentage that advances every poll and an expected finish time ("listo ~21:40"). Only *active* time counts, so suspending for a recording does not consume the estimate. Factors are learned from this machine's completed files (median of the last 20 samples per configuration, ≥3 to take over from the documented default) in a small local file. The queue summary carries the whole run's finish time. Stale performance claims in `CLAUDE.md` and the preset hint get corrected.

## Technical Context

**Language/Version**: Python 3.11.9 (Recorder `.venv`)

**Primary Dependencies**: New pure-Python module `app/transcription/eta.py`; existing worker/`queue_status`/window. No new third-party dependency; no Transcriptor change (it provides no duration or ETA).

**Storage**: New `%LOCALAPPDATA%\MeetingRecorder\transcripts\speed.json` (samples per configuration key, last 20 each). Job JSON unchanged. Estimate values travel only in the UI snapshot (`progress`, `eta_epoch`, batch fields).

**Testing**: unittest with an injected clock — `tests/test_eta.py` (pure model: weighting, revision, pause, unknown duration, rounding/day labels, learning threshold) and an extension of `tests/test_batch_tracking.py` (the monitor loop emits a weighted percentage and a finish time, frozen while suspended).

**Target Platform**: Windows desktop (Grabador)

**Project Type**: Desktop app (PySide6) + sibling CLI subprocess

**Performance Goals**: Estimate recomputed on the existing 1 s poll; WAV duration from file size (no process, no decode); `speed.json` read once per worker start, written once per completed file.

**Constraints**: Recording Always Wins — paused time must not count; estimates are advisory and must never influence scheduling or retries; local-only history (no upload); no false precision (5-minute rounding).

**Scale/Scope**: One machine, four quality/PC-usage combinations in practice, batches up to ~10 files and ~24 h.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- I. Recording Always Wins — PASS (active-time accounting exists precisely so a recording pause does not corrupt the estimate; nothing about the estimate can start or resume work)
- II. Privacy Is Local — PASS (`speed.json` holds durations and elapsed seconds, stays in local app data, nothing leaves the machine)
- III. Transcription stays a sibling subprocess — PASS (no engine change; success still artifact-based; the estimate is cosmetic by construction)
- IV. Robust paths and processes — PASS (no new subprocess; duration from file size; `speed.json` lives beside the queue, outside OneDrive)
- V. Simplicity for a single power user — PASS (one pure module + one small JSON; no phase-weight model, no scheduler, no learning framework)
- Verification & Quality — PASS (pure functions with an injected clock; the monitor-loop test from 020 is extended rather than duplicated)

Post-design re-check: unchanged. Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/021-weighted-progress-eta/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/progress-estimate.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
app/transcription/eta.py            # NEW: wav duration, speed table + learning store, weighted progress, finish-time formatting
app/transcription/worker.py         # active-time accounting per live job; weighted progress + eta in _emit; record a sample on completion; run total
app/transcription/queue_status.py   # batch finish time in the summary; keep batch_suffix
app/ui/main_window.py               # notice shows "— listo ~21:40" (paused label when suspended); summary shows the run total
app/transcription/presets.py        # Equilibrado hint: measured factor instead of "~2×"
CLAUDE.md                           # corrected performance section (1.08× more CPU / 1.45× usable, n=22)

tests/test_eta.py                   # NEW: pure model with injected clock
tests/test_batch_tracking.py        # monitor loop emits weighted progress + finish time; frozen while suspended
```

**Structure Decision**: All arithmetic and formatting live in `eta.py` as pure functions plus one small persistence class, so every success criterion is testable without a process, a clock or Qt. The worker only feeds it observations (audio duration, active elapsed, transcription percentage, phase) and puts the results in the snapshot it already emits.

## Complexity Tracking

> No constitution violations; section intentionally empty.
