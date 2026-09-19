# Tasks: The estimate charges the model load once, not once per file

**Input**: [spec.md](./spec.md) · [plan.md](./plan.md) · [research.md](./research.md) · [data-model.md](./data-model.md)

**Baseline to beat** (measured 2026-09-18, see research.md): 45 s sample promised 90 s against 42–55 s real; 300 s samples promised 370 s against 313 s and 330 s real.

## Phase 1 — Tests first

- [x] **T001** `tests/test_eta.py`: a file that loads the models is charged the measured cost once; the same file reusing loaded models is charged nothing beyond `audio × factor`. (FR-001, FR-002, SC-002)
- [x] **T002** `tests/test_eta.py`: the charge lives in one named constant and matches what research.md measured; a zero or unknown duration still yields no estimate. (FR-004, FR-005)
- [x] **T003** `tests/test_batch_tracking.py`: with N pending files in one engine run, the batch estimate grows by work only — one load for the whole run, not N. (FR-003, SC-001)
- [x] **T004** `tests/test_eta.py`: the guarantees of spec 021 still hold with the new composition — never promising the past, stretching when the estimate runs out, the 99 % ceiling, the floor from the engine's percentage. (FR-005)

## Phase 2 — Implementation

- [x] **T005** `app/transcription/eta.py`: `STARTUP_SECONDS` becomes the measured 12 s, documented with the method; `estimate_total_seconds` takes whether this file pays the load. (FR-001, FR-004)
- [x] **T006** `app/transcription/eta.py`: `ProgressTracker.reset` accepts and forwards that decision. (FR-002)
- [x] **T007** `app/transcription/worker.py`: the first live file of a run we started pays the load; a file promoted inside a running engine does not; an adopted process is already warm. (FR-002)
- [x] **T008** `app/transcription/worker.py`: `_batch_eta` adds work only for the pending files of the run. (FR-003)

## Phase 3 — Documentation

- [x] **T009** `CLAUDE.md`: the measured load cost, how it was measured, and the once-per-run rule, next to the existing speed figures. (FR-004)
- [x] **T010** `specs/025-startup-charged-once/quickstart.md`: how to reproduce the measurement and the acceptance run.

## Phase 4 — Verification

- [x] **T011** Full suite green (`unittest discover -s tests`).
- [x] **T012** `verify_transcription.py --quick` still passes end to end against the real engine.
- [x] **T013** Acceptance re-run with two samples of 300 s: each file's first promise within 15 % of real (baseline +12 % and +18 %). (SC-003)
- [x] **T014** Acceptance re-run with samples of 45 s: promise under twice the real time (baseline 90 s against 42 s). (SC-004)
- [x] **T015** The acceptance criteria of specs 020, 021 and 024 still hold in the same runs: one live file, no stale name, percentage advancing during speaker identification, truthful phases. (SC-005)
