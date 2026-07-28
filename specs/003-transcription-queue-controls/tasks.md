# Tasks: Transcription Queue Controls

**Input**: Design documents from `/specs/003-transcription-queue-controls/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Focused unit tests for JobStore cancel/clear + language normalize (high value, pure).

**Organization**: By user story; MVP = US1 + US2; US3 included (small).

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

- [X] T001 Confirm feature dir + `feature.json` point at `specs/003-transcription-queue-controls`
- [X] T002 [P] Skim `jobs.py` / `worker.py` / TX banner in `main_window.py` against contracts

---

## Phase 2: Foundational

- [X] T003 Add `CANCELLED = "cancelled"` and helpers `normalize_language` in `app/transcription/jobs.py` (or tiny helper colocated)
- [X] T004 Implement `JobStore.cancel` + `JobStore.clear_failed` (+ optional `delete`) in `app/transcription/jobs.py`
- [X] T005 [P] Unit tests for cancel pending, clear_failed scope, normalize_language in `tests/test_transcription_queue_controls.py`

**Checkpoint**: Store API ready

---

## Phase 3: User Story 1 - Cancel (P1) 🎯 MVP

**Goal**: Cancel pending/running jobs from UI; stop sibling process

**Independent Test**: Cancel mid-job → status cancelled; process gone

- [X] T006 [US1] `TranscriptionWorker.cancel(job_id)`: store cancel, terminate owned PID, emit snapshot; honor cancelled in `_settle` (no auto-retry) in `app/transcription/worker.py`
- [X] T007 [US1] Banner **Cancelar** button + wire `_cancel_transcription` in `app/ui/main_window.py`

**Checkpoint**: US1 testable

---

## Phase 4: User Story 2 - Language UI (P1)

**Goal**: Language combo persisted and snapshotted at enqueue

- [X] T008 [US2] Normalize `transcription_language` on `AppConfig.load`/`save` in `app/core/config.py`
- [X] T009 [US2] Idioma combo (`es`/`en`/`auto`) next to presets; save on change; pass normalized language on enqueue in `app/ui/main_window.py`

**Checkpoint**: US2 testable

---

## Phase 5: User Story 3 - Clear failed (P2)

**Goal**: Remove error/cancelled queue files from UI

- [X] T010 [US3] `TranscriptionWorker.clear_failed` + UI **Limpiar fallidos** visibility/handler in `app/transcription/worker.py` and `app/ui/main_window.py`

**Checkpoint**: US3 testable

---

## Phase 6: Polish

- [X] T011 [P] Run unit tests; smoke that Recording Always Wins paths untouched
- [ ] T012 Manual pass of `quickstart.md` steps 1–7 (or note deferred to user)

---

## Dependencies

- T003–T004 before T005–T006
- T006 before T007
- T008 before T009
- T004 before T010
- T007/T009/T010 before T011

## Parallel

- T002 ∥ T001
- T005 after T004 (tests can follow impl closely)
- T008 ∥ T006 after foundational

## MVP

Ship T001–T010; T012 may be user-validated.
