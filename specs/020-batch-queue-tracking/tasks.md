# Tasks: Truthful tracking of a multi-file transcription batch

**Input**: Design documents from `/specs/020-batch-queue-tracking/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included (the monitoring loop had no coverage; SC-006 requires it)

**Organization**: Tasks are grouped by user story.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

**Purpose**: Point the active feature at 020

- [x] T001 Persist `feature_directory` to `specs/020-batch-queue-tracking` in `.specify/feature.json`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Parse the engine's log without Qt and without a process, so every story can be tested

**⚠️ CRITICAL**: No user story work until this phase is complete

- [x] T002 Create `app/transcription/cli_progress.py` with `parse_plain_chunk()` returning `(stage, pct, cli_name, note)` per contract `contracts/cli-progress-log.md`: `> Procesando:` resets `pct` to 0, `transcribiendo... NN%` sets it, diarization returns `-1` (indeterminate)
- [x] T003 Add name matching to `app/transcription/cli_progress.py`: `cli_name_for_job()`, `job_matches_cli_name()`, `job_for_cli_name()` comparing file names/stems (accents, spaces, brackets), never full paths
- [x] T004 Add per-file slicing to `app/transcription/cli_progress.py`: `log_section_for()`, `error_in_section()`, `section_ended_in_diarization()` (empty slice = never started)
- [x] T005 Replace the worker's local regexes with `cli_progress` in `app/transcription/worker.py` (`_parse_log` now also returns the engine's current file)

**Checkpoint**: Parsing is unit-testable in isolation

---

## Phase 3: User Story 1 - Know what is actually happening in a long batch (Priority: P1) 🎯 MVP

**Goal**: One file in progress, the rest waiting, ready files leaving the list as their transcript appears, and a notice that names the real file plus its position

**Independent Test**: Drive `_monitor` with a step-by-step batch log and compare states/emissions against the log and the transcripts on disk

### Tests for User Story 1

- [x] T006 [P] [US1] `tests/test_cli_progress.py`: file switch resets the percentage, diarization blanks it, real meeting names (accents/brackets) match their job
- [x] T007 [P] [US1] `tests/test_queue_status.py`: a batch whose members are all `running` renders exactly one `En curso` and the rest `En espera`; `queue_counts(live_id)` reports 1 in progress; `batch_suffix()` only for real batches
- [x] T008 [US1] `tests/test_batch_tracking.py`: drive the real `_monitor` loop with a fake process writing the log in steps — live switching, ready-on-transcript, indeterminate progress during diarization, banner following the live file with `batch_pos`/`batch_total`

### Implementation for User Story 1

- [x] T009 [US1] In `_execute` (`app/transcription/worker.py`) mark only the lead `running`; other batch members keep `pending` with the run's `pid` and shared `log_path`
- [x] T010 [US1] Add `_cohort()`, `_reload()`, `_output_ready()`, `_harvest_ready()` to `app/transcription/worker.py`: settle any member as `done` the moment its `transcripcion.txt` exists (INV-2)
- [x] T011 [US1] Add `_activate_live()` + `_next_in_cohort()` to switch the live job on `> Procesando:` and after a completion, closing out the previous one (done if it has a result, else back to `pending`)
- [x] T012 [US1] Map indeterminate progress in `_monitor` (`_ui_progress`: `-1` → `None`) and only emit when something actually changed
- [x] T013 [US1] Add `_batch_position()` and emit `batch_pos` / `batch_total` in `_emit` (0/0 for single-file jobs)
- [x] T014 [US1] `queue_counts(live_id)` in `app/transcription/jobs.py`: a `running` member that is not the live one counts as waiting
- [x] T015 [US1] `format_queue_line(..., live_id=)` in `app/transcription/queue_status.py`: non-live `running` members render as `⏳ … En espera`; add `batch_suffix()`
- [x] T016 [US1] `app/ui/main_window.py`: `_tx_live_id()`, banner follows the live file with `batch_suffix`, refresh no longer hijacks the selection (keeps it only on failed/cancelled rows), `queue_counts(live_id)` for the summary, hide the stale import hint while something runs, ignore selection of waiting members
- [x] T017 [US1] Keep the per-file system notification when the batch continues (`_notify_tx_done` in `app/ui/main_window.py`)

**Checkpoint**: US1 verifiable with unittest and against a real batch log (quickstart §3)

---

## Phase 4: User Story 2 - Each file's outcome is its own (Priority: P2)

**Goal**: One file's error, OOM or diarization failure never changes another member's state, retries or quality settings

**Independent Test**: A batch log where exactly one file fails; assert the others are untouched

### Tests for User Story 2

- [x] T018 [P] [US2] `tests/test_batch_tracking.py::TestPerFileAttribution`: the error belongs to its own file, "died in diarization" is scoped to the last file, a file that never started has no section
- [x] T019 [P] [US2] `tests/test_batch_tracking.py`: a cancelled member is not resurrected when the engine reaches its name; a member skipped without a result returns to `pending`

### Implementation for User Story 2

- [x] T020 [US2] `_settle` in `app/transcription/worker.py` uses `_log_section(job)` for the error line, the OOM check and the diarization check (no whole-log reads); drop `_last_error_line` / `_log_is_oom` / `_last_stage_was_diarization`
- [x] T021 [US2] `_activate_live` refuses to promote `done` / `error` / `cancelled` jobs (INV-3)
- [x] T022 [US2] `cancel()` kills the child only when the cancelled job is the live one; other members of that run return to `pending`
- [x] T023 [US2] Human-readable failure reason via `_why_no_result()` (no `exit code None`); `_settle` is idempotent for jobs already `done`
- [x] T024 [US2] Clear `pid` when a job reaches `done` so cohorts never group historical jobs after PID reuse

**Checkpoint**: A failing file in a batch costs only that file

---

## Phase 5: User Story 3 - The queue does not leave junk behind (Priority: P3)

**Goal**: Intermediate audio of finished jobs is reclaimed automatically; active jobs are untouched

**Independent Test**: Leave work audio for a finished job and an active one; run the purge; only the finished one disappears

### Tests for User Story 3

- [x] T025 [P] [US3] `tests/test_batch_tracking.py::TestWorkDirHousekeeping`: purges finished and unknown job directories, preserves active ones, reports bytes reclaimed

### Implementation for User Story 3

- [x] T026 [US3] `JobStore.purge_orphan_work_dirs()` in `app/transcription/jobs.py` (returns bytes reclaimed)
- [x] T027 [US3] Call it at the end of `_reconcile` in `app/transcription/worker.py` (app start)

**Checkpoint**: `transcripts\work\` is empty after a session with no active jobs (468.6 MB reclaimed on the audited machine)

---

## Phase 6: Polish & Documentation

- [x] T028 [P] Record the new invariants in `CLAUDE.md`: one live job per batch, log read by sections, `purge_orphan_work_dirs` at reconcile
- [x] T029 Full suite green (`python -m unittest discover -s tests -q`): 131 tests
- [ ] T030 Manual acceptance on the next real multi-file batch per `quickstart.md` §3 (needs a restart of the app to pick up the worker changes) — pending user run

---

## Phase 7: Remediation from `/speckit-analyze` (see analyze.md)

- [x] T031 [F1] Restrict `_cohort()` in `app/transcription/worker.py` to open jobs (`pending`/`extracting`/`running`) so recycled pids cannot attach historical `done` jobs to a live batch and inflate `archivo N de M`
- [x] T032 [F2] Add an explicit SC-003 assertion in `tests/test_batch_tracking.py`: once a file is announced as ready, no later in-progress emission may name it

---

## Dependencies

- Phase 2 (T002–T005) blocks everything else.
- US1 (T006–T017) is the MVP and is independent of US2/US3.
- US2 (T018–T024) only needs Phase 2 (`log_section_for`), not US1.
- US3 (T025–T027) is fully independent.
- T030 is the only task that needs a real engine run.

## Notes

- `[P]` tasks touch different files and can run in parallel.
- No Transcriptor change: the CLI contract stays exactly as documented in `contracts/cli-progress-log.md`.
- Out of scope (own features): weighted progress + ETA, queue history pruning, making `verify_transcription.py --quick` runnable.
