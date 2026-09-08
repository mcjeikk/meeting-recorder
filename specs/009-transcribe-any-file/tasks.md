# Tasks: Transcribe Any Audio File

**Input**: Design documents from `/specs/009-transcribe-any-file/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Unit tests for extensions, classify/enqueue/path handling (requested). Headless UI optional.

**Organization**: By user story. MVP = US1 (picker + same queue). US2 drop. US3 errors/copy.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup

**Purpose**: Confirm artifacts and touch points

- [X] T001 Confirm `.specify/feature.json` and `specs/009-transcribe-any-file/` are the active feature
- [X] T002 [P] Skim `app/transcription/jobs.py`, `worker.py`, `integration.py`, TX block in `app/ui/main_window.py` against `contracts/ui-transcribe-file.md`

---

## Phase 2: Foundational (Blocking)

**Purpose**: Import classification helper used by all stories

**⚠️ CRITICAL**: No user story UI until this phase is complete

- [X] T003 Add `SUPPORTED_MEDIA_EXTS`, `is_supported_media`, `ImportKind` / `ImportResult`, and `classify_import` in `app/transcription/import_media.py`
- [X] T004 Implement `enqueue_imports` in `app/transcription/import_media.py` (absolute paths, snapshot preset/language, never copy original, skip duplicates)
- [X] T005 [P] Unit tests for extensions, missing file, folder, already_active, already_done, enqueue path in `tests/test_transcribe_any_file.py`

**Checkpoint**: Helper + tests green without UI

---

## Phase 3: User Story 1 - Transcribe from picker (P1) 🎯 MVP

**Goal**: Visible **Transcribir archivo…** enqueues onto the existing queue with current preset/language

**Independent Test**: Pick a supported file → banner shows job; original file unmoved; same cancel/open as meetings

### Tests for User Story 1

- [X] T006 [P] [US1] Headless test that MainWindow builds (no `show()`) and exposes the import button, in `tests/test_transcribe_any_file.py`

### Implementation for User Story 1

- [X] T007 [US1] Add **Transcribir archivo…** + hint in group 4 of `app/ui/main_window.py` (distinct from checkbox and Grabar)
- [X] T008 [US1] Wire picker (`QFileDialog.getOpenFileNames`), call `enqueue_imports`, apply non-modal status/banner feedback in `app/ui/main_window.py`
- [X] T009 [US1] Enable/disable import button with other TX controls when Transcriptor missing in `app/ui/main_window.py`
- [X] T010 [US1] Soften worker missing-file copy so it fits imported files in `app/transcription/worker.py`

**Checkpoint**: US1 testable from UI picker

---

## Phase 4: User Story 2 - Drag and drop (P2)

**Goal**: Drop files on the window; overlay; same enqueue path

**Independent Test**: Drop supported file(s) → queued; drop `.txt`/folder → message, no job

- [X] T011 [P] [US2] Tests for multi-path `enqueue_imports` (mixed valid/invalid) in `tests/test_transcribe_any_file.py`
- [X] T012 [US2] `setAcceptDrops`, drag overlay, `dropEvent` using `enqueue_imports` in `app/ui/main_window.py`

**Checkpoint**: Picker and drop share one helper

---

## Phase 5: User Story 3 - Errors, duplicates, recording (P2)

**Goal**: Clear in-window errors; already-done opens existing; import allowed while recording

**Independent Test**: Unsupported type, done duplicate, and (manual) import-during-record

- [X] T013 [US3] already_done / already_active messages + Abrir when result exists in `app/ui/main_window.py`
- [X] T014 [US3] Confirm import button/drop stay available while recording (do not disable on `_set_recording_ui`) in `app/ui/main_window.py`

**Checkpoint**: Error and recording cases covered

---

## Phase 6: Polish

- [X] T015 [P] Mention **Transcribir archivo…** in `README.md` (transcription section only)
- [X] T016 Run `tests/test_transcribe_any_file.py` plus existing `tests/test_transcription_queue_controls.py` and `tests/test_recording_names.py`
- [ ] T017 Manual pass of `specs/009-transcribe-any-file/quickstart.md` (or defer to user)

---

## Dependencies

- T003–T004 before T005–T008
- T007 before T008–T009
- T004 before T011–T012
- T008 before T013
- T012/T014 after T007 (same file — sequential)
- T016 after implementation tasks

## Parallel

- T001 ∥ T002
- T005 after T004 (tests follow helper)
- T006 ∥ T007 after foundation (test vs button; merge carefully)
- T011 ∥ T010 (tests vs worker copy)

## MVP

Ship T001–T010 (picker). T011–T014 complete the requested UX. T017 may be user-validated.

## Implementation Strategy

1. Foundation helper + unit tests
2. US1 picker (MVP)
3. US2 drop
4. US3 duplicate/recording polish
5. README + unittest run
