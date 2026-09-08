# Tasks: Selected Recordings Folder for Conversion Outputs

**Input**: Design documents from `/specs/010-selected-folder-outputs/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Required (user request + SC-001). unittest proving after changing output dir, conversion/transcript paths resolve to the new folder.

**Organization**: By user story. MVP = US1 (persist + absolute meeting/transcript paths).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup

**Purpose**: Confirm active feature and touch points

- [X] T001 Confirm `.specify/feature.json` points at `specs/010-selected-folder-outputs/`
- [X] T002 [P] Skim `app/core/config.py`, `app/ui/main_window.py` (`_choose_output`, `_build_settings`, `_save_config`), `app/transcription/integration.py` (`output_dir_for`, `build_command`), `app/transcription/jobs.py` (`enqueue`) against `research.md` and `contracts/ui-output-folder.md`

---

## Phase 2: Foundational (Blocking)

**Purpose**: Path helpers all stories share

**⚠️ CRITICAL**: No UI wiring until resolve helpers exist

- [X] T003 Add `resolve_output_dir` in `app/core/config.py` (expanduser + resolve; never substitute `default_output_dir()` after a user path is given)
- [X] T004 Make `output_dir_for` and `result_dir_for` return absolute paths under the media parent in `app/transcription/integration.py`
- [X] T005 Canonicalize `media_path` to an absolute path in `JobStore.enqueue` in `app/transcription/jobs.py`

**Checkpoint**: Helpers ready; tests in US1 will fail until T003–T005 + persist are done

---

## Phase 3: User Story 1 - New meetings follow the chosen folder (P1) 🎯 MVP

**Goal**: After Cambiar… to folder B, next meeting MP4 and user-visible `Transcripciones/<stem>/` (CLI `--output`) are under B, absolute, persisted across restart

**Independent Test**: `python -m unittest tests.test_selected_folder_outputs -v` plus manual record into B

### Tests for User Story 1

- [X] T006 [P] [US1] Write failing tests in `tests/test_selected_folder_outputs.py`: resolve vs default; after “change” to B, recording dest, `output_dir_for`/`result_dir_for`, and `build_command` `--output` are absolute under B (not default, not LOCALAPPDATA, not relative)

### Implementation for User Story 1

- [X] T007 [US1] Persist resolved folder immediately in `_choose_output` in `app/ui/main_window.py` (`AppConfig.output_dir` + `save()`)
- [X] T008 [US1] Use `resolve_output_dir` in `_build_settings` (and `_save_config` path) in `app/ui/main_window.py` so mux writes `{B}/{stem}.mp4`
- [X] T009 [US1] Confirm worker still passes `output_dir_for(media)` into `build_command` in `app/transcription/worker.py` (absolute after T004); no Transcriptor source edits

**Checkpoint**: US1 tests green; relative `--output` cannot land in Transcriptor RAIZ

---

## Phase 4: User Story 2 - Open folder matches selected meeting (P2)

**Goal**: Open-recordings / open-transcript for a meeting saved in B show paths under B

**Independent Test**: After US1, `_last_output` dirname and `result_dir` are under B

- [X] T010 [P] [US2] Assert in `tests/test_selected_folder_outputs.py` that open-folder candidates (`Path(mp4).parent` and `result_dir_for(mp4)`) live under the selected B
- [X] T011 [US2] Keep `_open_output_folder` using the finished MP4 path in `app/ui/main_window.py` (already dirname of `_last_output`); only adjust if it still reads stale `AppConfig.output_dir`

**Checkpoint**: Opening Explorer cannot point at folder A after a B meeting

---

## Phase 5: User Story 3 - Imports and old files stay put (P3)

**Goal**: Imports and jobs for files still in A do not copy into B; new recordings still use B

**Independent Test**: `result_dir_for` on a file in A stays under A; import tests in `tests/test_transcribe_any_file.py` still pass

- [X] T012 [P] [US3] Test in `tests/test_selected_folder_outputs.py` that `result_dir_for` for media in A is under A even when `AppConfig.output_dir` is B
- [X] T013 [US3] Do not add copy-into-recordings-folder logic in `app/transcription/import_media.py`; re-run `tests.test_transcribe_any_file`

**Checkpoint**: 009 layout unchanged

---

## Phase 6: Polish

- [X] T014 [P] If README folder layout is wrong after this fix, align the Transcripciones paragraph in `README.md` (only if needed)
- [X] T015 Run `.\.venv\Scripts\python.exe -m unittest tests.test_selected_folder_outputs tests.test_transcribe_any_file tests.test_recording_names -v` per `quickstart.md`

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 (T003–T005) → US1 tests (T006) should fail → T007–T009 → T006 pass
- US2/US3 after US1 path helpers (T004)
- T014–T015 last

### Parallel opportunities

- T002 with T001
- T006 can be written in parallel with T003 once the public function names are agreed
- T010 and T012 after T004
- T014 with T015 after implementation

### MVP

T001–T009 (persist + absolute conversion/transcript paths + tests)

## Notes

- Do not merge Recorder/Transcriptor venvs
- Do not commit or push
- Do not revert unrelated dirty work (009, Spec Kit, window-title naming) unless required to compile
