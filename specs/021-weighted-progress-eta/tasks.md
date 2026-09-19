# Tasks: Progress that means something, and a time estimate

**Input**: Design documents from `/specs/021-weighted-progress-eta/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/progress-estimate.md

**Tests**: Included (every success criterion is checkable with pure functions + an injected clock)

**Organization**: Tasks are grouped by user story.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

- [x] T001 Point `.specify/feature.json` at `specs/021-weighted-progress-eta`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The estimate model, testable without a process, a real clock or Qt

**⚠️ CRITICAL**: No user story work until this phase is complete

- [x] T002 Create `app/transcription/eta.py` with `wav_duration_seconds(path)` (16 kHz mono PCM: `(size − 44) / 32000`; 0.0 when missing/too small)
- [x] T003 Add the speed table and keys to `app/transcription/eta.py`: `speed_key(model, no_diarize, pc_impact)` and `DEFAULT_FACTORS` per research R6 (documented measured values)
- [x] T004 Add `SpeedStore` to `app/transcription/eta.py`: load/save `speed.json`, `record(key, audio_s, active_s)` (skip audio < 60 s, keep last 20), `factor_for(key)` (own median at ≥3 samples, else default), never raise on a corrupt file (L-1..L-5)
- [x] T005 Add `estimate_total_seconds(audio_s, factor)` with the documented startup allowance, and `weighted_progress(...)` implementing E-2..E-7 (monotonic, ASR floor, 99% cap, estimate extension, unknown duration)
- [x] T006 Add `format_finish(now, eta_epoch)` to `app/transcription/eta.py`: round up to 5 minutes, `listo ~HH:MM` / `listo mañana ~HH:MM` / `listo el <día> ~HH:MM` (E-8)

**Checkpoint**: The model is complete and unit-testable in isolation

---

## Phase 3: User Story 1 - Know how long this will take (Priority: P1) 🎯 MVP

**Goal**: The notice shows the expected finish time of the file in progress, and the queue summary the whole run's

### Tests for User Story 1

- [x] T007 [P] [US1] `tests/test_eta.py`: WAV duration from size; default vs learned factor (switch at the third sample, survives reload, corrupt file behaves as empty)
- [x] T008 [P] [US1] `tests/test_eta.py`: finish-time formatting (5-minute rounding up, today / tomorrow / later day), never a past time
- [x] T009 [US1] `tests/test_batch_tracking.py`: the monitor loop emits `eta_epoch` for the live file and a run total for the batch; unknown duration emits neither

### Implementation for User Story 1

- [x] T010 [US1] Track active elapsed per attempt in `_monitor` (`app/transcription/worker.py`): accumulate only while the child runs and is not suspended (E-6)
- [x] T011 [US1] Compute the estimate each poll in `_monitor` using the live job's audio duration and its configuration factor; put `eta_epoch` / `eta_paused` in the snapshot via `_emit`
- [x] T012 [US1] Compute the run total in `_monitor` (remainder of the live file + `audio × factor` of unfinished members) and emit it as `batch_eta_epoch`
- [x] T013 [US1] Record a sample on successful completion in `_settle` (`SpeedStore.record`) using the file's audio duration and its active time
- [x] T014 [US1] Show `— listo ~HH:MM` after the batch position in the notice (`app/ui/main_window.py`), and `estimación en pausa` while suspended
- [x] T015 [US1] Add the run total to the queue summary in `app/transcription/queue_status.py` + `app/ui/main_window.py` (`lote listo ~HH:MM`)

**Checkpoint**: A user can answer "will this be done before I need the laptop?" from the notice (SC-005)

---

## Phase 4: User Story 2 - A percentage that reflects real work (Priority: P2)

**Goal**: The bar advances through speaker identification instead of stalling at 90%

### Tests for User Story 2

- [x] T016 [P] [US2] `tests/test_eta.py`: progress advances while the stage is speaker identification, is monotonic, is floored by the transcription percentage, caps at 99 until done, and the estimate extends past 100% of the original total
- [x] T017 [P] [US2] `tests/test_eta.py`: a file with speakers disabled reaches 100 without waiting for that phase
- [x] T018 [US2] `tests/test_batch_tracking.py`: the emitted percentage during speaker identification is a number that grows (spec 020 only required "no stale number")

### Implementation for User Story 2

- [x] T019 [US2] Replace the raw transcription percentage with the weighted one in the snapshot emitted by `_monitor` / `_emit`, keeping the indeterminate case for unknown duration (INV-4)
- [x] T020 [US2] Reset progress accounting on file switch and on a new attempt, preserving spec 020 behavior (FR-003)

**Checkpoint**: The bar and the finish time tell the same story

---

## Phase 5: Documentation correction (part of this feature, FR-011)

- [x] T021 [P] Correct the performance section of `CLAUDE.md`: measured 1.08× (more CPU, n=18) and 1.45× (PC usable, n=2) instead of "2–2.5×"; drop the stale "diarization takes 1 h 13 for a 1 h meeting" claim
- [x] T022 [P] Correct the Equilibrado hint in `app/transcription/presets.py` ("~2× la duración del audio" → measured value), keeping the wording short for the UI
- [x] T023 [P] Mention the estimate and where history lives in `README.md`

---

## Phase 6: Polish

- [x] T024 Full suite green (`python -m unittest discover -s tests -q`)
- [x] T025 Manual acceptance per `quickstart.md` §3 — **run 2026-09-18** on real batches (three samples of 45 s, then two of 300 s; speakers on, "Usar más CPU"):
  - **the frozen percentage is gone**: during speaker identification the bar ran 40 → 81 % and 40 → 85 % on the 300 s samples (and 32 → 45, 34 → 46, 30 → 37 on the 45 s ones), refreshing every 15 s with no log line to go by
  - the finish time was always present and never sat in the past (52 notices with a time, 0 expired at emission)
  - the whole 300 s batch took 648 s for 600 s of audio — **1.08×**, matching the factor documented in `CLAUDE.md`
  - **accuracy was the one criterion that failed**: 370 s promised against 313 s and 330 s real (+18 % and +12 %). Root cause measured and fixed in spec 025 — the model load was charged to every file instead of once per engine run, and the constant was over three times the measured cost

---

## Phase 7: Remediation from `/speckit-analyze` (see analyze.md)

- [x] T026 [G7] Keep the speed history beside its queue (`SpeedStore(store.base / "speed.json")` in `app/transcription/worker.py`) so a temporary queue (tests, `verify_transcription.py`) never writes the machine's real history
- [x] T027 [G7] Reject implausible samples in `SpeedStore.record` (active time under 30 s, or a factor outside 0.1–8×) and cover it in `tests/test_eta.py`; delete the poisoned real `speed.json`

---

## Dependencies

- Phase 2 (T002–T006) blocks US1 and US2.
- US1 (T007–T015) is the MVP; US2 (T016–T020) refines the same numbers and can follow independently.
- Phase 5 is documentation-only and parallel to everything.
- T025 needs a real transcription.

## Notes

- `[P]` tasks touch different files.
- No Transcriptor change; the engine provides no duration or estimate (research R1).
- Estimates stay advisory: no scheduling or retry decision may read them (E-1).
