# Tasks: The queue forgets what it no longer needs

**Input**: Design documents from `/specs/023-queue-history-pruning/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/queue-retention.md

**Tests**: Included (the whole decision is a pure function over synthetic records with an injected clock)

**Organization**: Tasks are grouped by user story.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

- [x] T001 Point `.specify/feature.json` at `specs/023-queue-history-pruning`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The retention decision, testable without a filesystem or a clock

**⚠️ CRITICAL**: No user story work until this phase is complete

- [x] T002 Create `app/transcription/retention.py` with `HISTORY_DAYS = 30` and `MAX_HISTORY = 200` as the single source of the limits (FR-010)
- [x] T003 Add `job_age_key(job)` to `app/transcription/retention.py`: `finished_at` → `created_at` → oldest-possible, parsing ISO local strings and never raising (R-3, R-4, INV-2)
- [x] T004 Add `prunable_job_ids(jobs, *, now, days, max_history)`: only `done`, prune when outside the window **or** beyond the newest `max_history` (R-1, R-2, R-5, INV-1, INV-5)
- [x] T005 Add `prunable_log_paths(log_dir, surviving_jobs)`: every `*.log` no surviving record claims, matched by `log_path` and by the `_<id>.log` suffix (R-6, INV-6)

**Checkpoint**: The rule is complete and unit-testable in isolation

---

## Phase 3: User Story 1 - The app stays as fast on month six as on day one (Priority: P1) 🎯 MVP

**Goal**: Finished records stop accumulating, silently, at startup

### Tests for User Story 1

- [x] T006 [P] [US1] `tests/test_retention.py`: records older than the window are prunable; records inside it are not; the boundary is inclusive-safe
- [x] T007 [P] [US1] `tests/test_retention.py`: with more than `MAX_HISTORY` finished records, exactly the newest `MAX_HISTORY` survive
- [x] T008 [P] [US1] `tests/test_retention.py`: `pending`, `extracting`, `running`, `error` and `cancelled` records are never prunable, however old (INV-1)
- [x] T009 [P] [US1] `tests/test_retention.py`: a record with an empty or corrupt timestamp is prunable rather than immortal, and nothing raises (INV-2)
- [x] T010 [P] [US1] `tests/test_retention.py`: `JobStore.prune_history` deletes the chosen records, returns the counts, and a second call removes nothing (A-6, INV-3)
- [x] T011 [P] [US1] `tests/test_retention.py`: 300 synthetic records over a year are pruned to the limits in one pass, well under a second (SC-001, SC-002)

### Implementation for User Story 1

- [x] T012 [US1] Add `JobStore.prune_history(*, now=None) -> dict` to `app/transcription/jobs.py`: apply the decision, delete records then logs, guard every unlink, write nothing (A-1..A-5)
- [x] T013 [US1] Call it from `TranscriptionWorker._reconcile()` in `app/transcription/worker.py`, right after `purge_orphan_work_dirs()`, emitting nothing (C-1, C-3, FR-005)

**Checkpoint**: Startup bounds the queue and the user sees no difference

---

## Phase 4: User Story 2 - An already transcribed file is still recognised after pruning (Priority: P1)

**Goal**: Pruning a record never causes hours of repeated transcription

### Tests for User Story 2

- [x] T014 [P] [US2] `tests/test_import_media.py`: no record + `transcripcion.txt` on disk ⇒ `ALREADY_DONE` with the resolved result folder, and nothing queued (T-3, INV-8)
- [x] T015 [P] [US2] `tests/test_import_media.py`: no record + no transcript ⇒ `OK` and queued (T-4, INV-9)
- [x] T016 [P] [US2] `tests/test_import_media.py`: an existing record still wins (message and result folder unchanged) and the summary wording is unchanged (T-2, T-6)

### Implementation for User Story 2

- [x] T017 [US2] Add `transcript_exists(media_path, output_base=None)` to `app/transcription/integration.py` (existence of `transcripcion.txt` in the resolved result folder; never raises) (T-1, T-5)
- [x] T018 [US2] Give `classify_import` an `output_base` parameter and fall back to `transcript_exists` when no record matches (T-2, T-3, T-4)
- [x] T019 [US2] Pass the configured output folder from `enqueue_imports` and its caller in `app/ui/main_window.py` so the check resolves the same destination the job would use

**Checkpoint**: Pruning is safe: an old recording re-added is still recognised

---

## Phase 5: User Story 3 - Logs stop accumulating on their own (Priority: P2)

**Goal**: Logs follow their records, and orphans disappear

### Tests for User Story 3

- [x] T020 [P] [US3] `tests/test_retention.py`: the log of a pruned record is deleted; the logs of live and failed records survive (SC-003, SC-005)
- [x] T021 [P] [US3] `tests/test_retention.py`: a log with no record at all is deleted; a locked/undeletable log does not abort the pass (INV-7)

### Implementation for User Story 3

- [x] T022 [US3] Delete pruned and orphan logs inside `prune_history`, counting them separately from records (FR-004)

**Checkpoint**: Every remaining log belongs to a record that still exists

---

## Phase 6: Documentation & Polish

- [x] T023 [P] Document the retention rule in `CLAUDE.md` (what the queue keeps, for how long, and why finished records are no longer the idempotence source)
- [x] T024 [P] Add one line to the `README.md` transcription section about the queue keeping recent history only
- [x] T025 [P] Write `specs/023-queue-history-pruning/quickstart.md`: how to inspect the queue, what a pass does, how to verify nothing of the user's moved
- [x] T026 Run the whole suite headless (`QT_QPA_PLATFORM=offscreen`, `PYTHONIOENCODING=utf-8`)
- [x] T027 Acceptance on the real queue: record the before/after record and log counts, confirm live/failed records and their logs survive, and re-run `verify_transcription.py --quick --no-speakers --seconds 20`

---

## Phase 7: Remediation from measurement and `/speckit-analyze` (see analyze.md)

- [x] T028 [G1] Add a per-pass deletion budget (`MAX_DELETIONS_PER_PASS = 100`, `oldest_first`) after a 300-record pass took 3.8 s on freshly written files; spec FR-012 / SC-002 updated with the real numbers instead of the guessed "well under a second"
- [x] T029 [G2] Put the US2 tests in the existing `tests/test_transcribe_any_file.py` (the import path's test file) rather than creating a second file for the same module

---

## Dependencies

- Phase 2 (T002–T005) blocks everything else: it is the rule.
- T012 depends on T004–T005; T013 depends on T012.
- T017 blocks T018, which blocks T019.
- Phase 5 is folded into `prune_history` (T022 extends T012) but is tested separately.
- Documentation (Phase 6) depends on the measured before/after from T027.

## Notes

- `[P]` tasks touch different files and can run in parallel.
- No Transcriptor change; no UI control (the user chose silent-at-startup).
- Failed and cancelled records keep their existing manual "clear" action; automatic pruning stays out of it.
