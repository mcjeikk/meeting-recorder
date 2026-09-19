# Implementation Plan: The estimate charges the model load once, not once per file

**Branch**: `025-startup-charged-once` | **Date**: 2026-09-18 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/025-startup-charged-once/spec.md`

## Summary

`estimate_total_seconds` stops adding the model load unconditionally. The caller says whether this file pays it: the first file of an engine run does, a file that reuses models already loaded in the same run does not. `worker._batch_eta` therefore adds bare work time for the pending files of the current run instead of one load each. The constant drops from 40 s to the 12 s measured on this machine (55 s and 54 s for a file that loads the models against 42 s for an equal-length file that reuses them, same configuration, 2026-09-18). Nothing else about the estimate changes: the stretch rule, the 99 % cap, the floor from the engine's own percentage and the learned factor all stay as spec 021 left them.

## Technical Context

**Language/Version**: Python 3.11.9 (Recorder `.venv`)

**Primary Dependencies**: none new; `eta.py` stays standard library only.

**Storage**: `speed.json` (the learned history) keeps its format. No migration: the change is in how the estimate is composed, not in what is stored.

**Testing**: unittest over pure arithmetic (`tests/test_eta.py`) for the charge itself, and `tests/test_batch_tracking.py` for the batch estimate under a simulated engine run. The end-to-end check is the acceptance script against the real engine, which produced the baseline numbers this feature must beat.

**Target Platform**: Windows desktop (Grabador)

**Project Type**: Desktop app (PySide6) + sibling CLI subprocess

**Performance Goals**: unchanged; the estimate is arithmetic per poll.

**Constraints**: the estimate stays advisory (no queue decision may read it); it must never promise a moment in the past; the learned factor's samples must stay comparable across files that load the models and files that do not.

**Scale/Scope**: one function signature in `eta.py`, one loop in `worker.py`, one constant.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- I. Recording Always Wins — PASS (the estimate counts active time only; suspension for a recording is untouched)
- II. Privacy Is Local — PASS (the history stays in `%LOCALAPPDATA%`)
- III. Transcription stays a sibling subprocess — PASS (this feature exists *because* one run carries several files; the engine is not touched)
- IV. Robust paths and processes — PASS (no paths, no processes; a missing duration still means "no estimate")
- V. Simplicity — PASS (a parameter and a constant; no new module, no learned second variable)
- Verification & Quality — PASS (the success criteria are numbers from a real batch, with a recorded baseline)

Post-design re-check: unchanged. Complexity Tracking empty.

## Design decisions

1. **Who decides whether the load is paid**: the caller, not the estimator. `eta.py` cannot know whether an engine is already warm — that is the worker's knowledge (it started the process and knows which file of the run is live). Passing a flag keeps the arithmetic pure and testable.
2. **First file of the run pays it, the rest do not** — instead of spreading the load across the run. The user reads each file's promise on its own, so an average would be wrong for every file rather than right for one.
3. **A constant, not a learned value.** The factor is already learned per machine and absorbs steady-state speed; the load is a small fixed cost. Learning it would need to separate load from processing inside a single measurement, which the log does not support today.
4. **12 s, from measurement.** Two independent differences on this machine (55 − 42 and 54 − 42) with identical audio length and configuration. Documented as measured, with the method, so a future machine can re-measure instead of guess.
5. **Speed samples stay as they are.** A first-file sample includes ~12 s of load over a run of minutes; the median over three or more samples absorbs it, and `MIN_SAMPLE_AUDIO_SECONDS` already rejects the short files where it would dominate.

## Project Structure

### Documentation (this feature)

```text
specs/025-startup-charged-once/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
app/transcription/eta.py     # STARTUP_SECONDS measured; estimate_total_seconds takes "does this file pay it?"
app/transcription/worker.py  # the live tracker and _batch_eta say who pays the load
CLAUDE.md                    # the measured load cost and the once-per-run rule

tests/test_eta.py            # the charge, its absence, and the guarantees of spec 021 preserved
tests/test_batch_tracking.py # batch estimate with N pending files carries one load, not N
```

**Structure Decision**: keep the estimate in `eta.py` and the knowledge of the engine run in `worker.py`, which is the split spec 021 already established. The worker is the only component that knows a run carries several files.

## Complexity Tracking

> No constitution violations; section intentionally empty.
