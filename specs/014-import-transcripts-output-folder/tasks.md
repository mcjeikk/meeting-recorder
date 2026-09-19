# Tasks: Imported Transcripts Follow Carpeta de Salida

**Input**: Design documents from `/specs/014-import-transcripts-output-folder/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included (TDD for path helpers and enqueue snapshot)

**Organization**: Tasks are grouped by user story.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

**Purpose**: Point the active feature at 014

- [x] T001 Persist `feature_directory` to `specs/014-import-transcripts-output-folder` in `.specify/feature.json`

---

## Phase 2: Foundational

**Purpose**: Path helpers and job snapshot used by every story

**⚠️ CRITICAL**: No user story work until this phase is complete

- [x] T002 Extend `output_dir_for` and `result_dir_for` in `app/transcription/integration.py` to honor optional `output_base` (absolute `{base}/Transcripciones`; empty/omitted → media parent)
- [x] T003 Add `output_base` on `TranscriptionJob` and `JobStore.enqueue(..., output_base=)` in `app/transcription/jobs.py` (canonicalize absolute; default empty = legacy)
- [x] T004 Pass `job.output_base` into `output_dir_for` / `result_dir_for` in `app/transcription/worker.py` (`build_command`, `_settle`, reconcile `transcripcion.txt`)

**Checkpoint**: Foundation ready

---

## Phase 3: User Story 1 - Imported transcripts land in Carpeta de salida (Priority: P1) 🎯 MVP

**Goal**: Import from folder A with Carpeta de salida B writes transcripts under B; original stays in A

**Independent Test**: unittest: `result_dir_for(media_a, output_base=B)` under B not A; enqueue stores `output_base`

### Tests for User Story 1

- [x] T005 [P] [US1] Replace `TestImportsStayBesideSource` in `tests/test_selected_folder_outputs.py` with tests that import media in A + `output_base=B` lands under B; empty `output_base` still uses parent; `enqueue` snapshots absolute `output_base`

### Implementation for User Story 1

- [x] T006 [US1] Pass resolved Carpeta de salida as `output_base` from `_import_media_paths` in `app/ui/main_window.py` into `TranscriptionWorker.enqueue`
- [x] T007 [US1] Add `output_base` to `TranscriptionWorker.enqueue` in `app/transcription/worker.py` and forward it to the store
- [x] T008 [US1] Keep `transcribe()` in `app/transcription/integration.py` using config `output_dir` when transcribing a path that is not already under that folder

**Checkpoint**: US1 testable via unittest without Qt

---

## Phase 4: User Story 2 - Meetings and in-flight jobs stay honest (Priority: P2)

**Goal**: Meeting mux+transcripts still under the video folder; queued jobs keep their snapshot

**Independent Test**: Existing meeting tests still pass; enqueue after record uses `Path(mp4).parent`

- [x] T009 [US2] Pass `output_base=Path(path).parent` from `_on_finished` in `app/ui/main_window.py` so a folder change mid-capture does not steal that meeting’s transcripts
- [x] T010 [US2] Confirm meeting-in-B tests in `tests/test_selected_folder_outputs.py` still pass with omitted `output_base` (parent is already B)

**Checkpoint**: US1 + US2

---

## Phase 5: User Story 3 - Copy and Abrir match Carpeta de salida (Priority: P3)

**Goal**: UI/docs do not claim imported results sit beside the source; Abrir uses stored `result_dir`

**Independent Test**: Hint text and README mention Carpeta de salida; already-done still uses `job.result_dir`

- [x] T011 [P] [US3] Update import hint in `app/ui/main_window.py` (results go to Carpeta de salida; original is not moved)
- [x] T012 [P] [US3] Align the Transcripciones paragraph in `README.md`
- [x] T013 [US3] Add a supersession note on FR-006 in `specs/009-transcribe-any-file/spec.md` and FR-006/US3 in `specs/010-selected-folder-outputs/spec.md`

**Checkpoint**: All stories

---

## Phase 6: Polish

- [x] T014 Run `tests.test_selected_folder_outputs` and `tests.test_transcribe_any_file` (and worker-related tests if enqueue signature changes)

---

## Dependencies & Execution Order

- Setup → Foundational (blocks stories) → US1 → US2 → US3 → Polish
- T005 can be written before T006–T008 (TDD); it depends on T002–T003 APIs
- T011/T012 parallel after US1 behavior exists

## Parallel Example: User Story 3

```text
T011 hint in main_window.py
T012 README.md
```

## Implementation Strategy

MVP is US1 (imports follow Carpeta de salida). US2 prevents meeting regressions. US3 is copy only.
