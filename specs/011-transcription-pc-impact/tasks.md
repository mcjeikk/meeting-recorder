# Tasks: Keep the PC Usable During Transcription

**Input**: Design documents from `/specs/011-transcription-pc-impact/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Required (SC-002 / FR-004 / FR-007). unittest for thread math, snapshot, legacy jobs, env.

**Organization**: By user story. MVP = US1 (control + launch constraints).

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

- [x] T001 Confirm `.specify/feature.json` points at `specs/011-transcription-pc-impact/`
- [x] T002 [P] Add `app/transcription/pc_impact.py` (ids, labels, `normalize_pc_impact`, `threads_for_impact`, `priority_class`, `thread_env`)

## Phase 2: Foundational

- [x] T003 Wire `cpu_threads_for_job` / `subprocess_env` / creationflags in `app/transcription/integration.py` to the profile helpers
- [x] T004 Add `transcription_pc_impact` to `AppConfig` in `app/core/config.py` (normalize on load/save; default usable)
- [x] T005 Snapshot `pc_impact` on `TranscriptionJob` / `JobStore.enqueue` in `app/transcription/jobs.py`; missing field on load → `full`

## Phase 3: User Story 1 — Choose PC impact (P1) 🎯 MVP

- [x] T006 [P] [US1] Write `tests/test_pc_impact.py`: normalize, thread table (8→4/6, 16→4/14), env keys, legacy job → full, new enqueue defaults usable, snapshot immutable
- [x] T007 [US1] Combo + hint + persist in `app/ui/main_window.py`; disable with other tx controls if tool missing
- [x] T008 [US1] `TranscriptionWorker` / `transcribe()` launch with job/config profile (`--threads`, env, flags)
- [x] T009 [US1] README + CLAUDE.md: usable default; quality vs PC use; torch/OpenMP cap

## Phase 4: User Story 2 — Best model + usable PC (P2)

- [x] T010 [P] [US2] Test enqueue Máxima + usable keeps `model=large-v3` and `pc_impact=usable`
- [x] T011 [US2] Record-finish and import enqueue paths pass current `pc_impact` in `app/ui/main_window.py`

## Phase 5: User Story 3 — Legacy + recording wins (P3)

- [x] T012 [US3] Confirm retry does not reset `pc_impact`; worker still suspends on `is_recording()` (no behavior change)
- [x] T013 [US3] Transcriptor `transcribe.py`: when `--threads N>0`, set OpenMP env (if unset) and `torch.set_num_threads(N)` best-effort

## Phase 6: Polish

- [x] T014 Run `python -m unittest tests.test_pc_impact tests.test_transcription_queue_controls tests.test_transcribe_any_file -v`
- [ ] T015 Manual pass of `quickstart.md` (optional; leave open if not run)

## FR coverage

| FR | Tasks |
|----|-------|
| FR-001–003, 011 | T004, T007 |
| FR-004, 007, 008 | T005, T006, T012 |
| FR-005, 006 | T002, T003, T008, T013 |
| FR-009, 012 | T010, T011 |
| FR-010 | T012 |
