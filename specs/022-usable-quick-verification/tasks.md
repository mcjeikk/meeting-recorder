# Tasks: A quick check that can actually be run

**Input**: Design documents from `/specs/022-usable-quick-verification/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/verify-cli.md

**Tests**: Included (the decisions the script makes are pure functions; the engine run is the manual acceptance)

**Organization**: Tasks are grouped by user story.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

- [x] T001 Point `.specify/feature.json` at `specs/022-usable-quick-verification`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Turn the script's decisions into importable functions and give it one throwaway home per run

**⚠️ CRITICAL**: No user story work until this phase is complete

- [x] T002 Restructure `verify_transcription.py` around module-level functions (`pick_recording`, `slice_args`, `build_sample`, `sandbox_paths`, `speakers_in_result`, `verdict`, `cleanup_sandbox`, `_parse_args`, `main`) so tests can import them without running the engine
- [x] T003 Create one sandbox per run (`tempfile.mkdtemp(prefix="verify_tx_")`) holding the queue (`tx/queue`, `tx/logs`, `tx/work`, `tx/speed.json`) and the destination (`salida/`) — V-1, INV-1, INV-2
- [x] T004 Define the exit codes as constants (0 pass · 1 wiring · 2 timeout · 3 environment · 130 interrupted) and return them from every path
- [x] T005 Refuse `--quick --force` with an explanatory message and clamp `--seconds` to a sane minimum (V-2)

**Checkpoint**: The script's decisions are testable and no run can write outside its sandbox

---

## Phase 3: User Story 1 - Check the wiring in a couple of minutes, safely (Priority: P1) 🎯 MVP

**Goal**: One command that proves the whole path and finishes in minutes without touching the user's data

### Tests for User Story 1

- [x] T006 [P] [US1] `tests/test_verify_quick.py`: `--quick --force` is refused; `--seconds 1` is refused; `--quick` defaults to a 60 s sample with speakers
- [x] T007 [P] [US1] `tests/test_verify_quick.py`: the slice is stream-copied with every stream mapped and passed as an argument list (V-4, V-5)
- [x] T008 [P] [US1] `tests/test_verify_quick.py`: queue and destination both resolve inside the sandbox (INV-1); newest recording is picked; an empty folder raises a clear error
- [x] T009 [P] [US1] `tests/test_verify_quick.py`: `cleanup_sandbox` removes a sandbox that still holds logs (INV-5)

### Implementation for User Story 1

- [x] T010 [US1] Cut the sample with `ffmpeg -ss 0 -t N -i <media> -map 0 -c copy` into the sandbox, named `<stem> [muestra Ns]<ext>`, and fail with exit 3 when the slice cannot be produced
- [x] T011 [US1] Enqueue the sample through the real `JobStore` in the sandbox and drive it with the real `TranscriptionWorker`, printing each update as it arrives
- [x] T012 [US1] Report the verdict block: sampled recording, sample length, elapsed time, artifacts, speakers, note, destination
- [x] T013 [US1] Fail with exit 3 and a plain message when the sibling engine or its `.venv` is missing (`integration.is_available`), instead of letting the job fail obscurely
- [x] T014 [US1] Keep the sandbox on failure, timeout and interruption (printing its path and the engine log) and delete it on success (INV-5, V-6)
- [x] T015 [US1] Stop the worker before cleanup (`TranscriptionWorker.shutdown(wait=...)` releasing the queue lock) and retry the delete, since Windows holds the lock file briefly

**Checkpoint**: `--quick` succeeds on a machine where every recording already has a transcript (SC-001) and leaves nothing behind (SC-003)

---

## Phase 4: User Story 2 - Verify the speaker path on demand (Priority: P2)

**Goal**: Catch the engine's silent degradation to "no speakers" without transcribing a whole meeting

### Tests for User Story 2

- [x] T016 [P] [US2] `tests/test_verify_quick.py`: speakers requested and zero reported is a failure naming the speaker path (INV-4); not requested, not required
- [x] T017 [P] [US2] `tests/test_verify_quick.py`: the count accepts the engine's real shape (a map `{SPEAKER_00: …}`), plus a list or a number, and an unreadable result counts as zero

### Implementation for User Story 2

- [x] T018 [US2] `--no-speakers` sets `no_diarize` on the queued job (fast variant); by default `--quick` verifies the speaker path
- [x] T019 [US2] Read `hablantes` from `transcripcion.json` and report the count; require ≥ 1 when speakers were requested (FR-006, SC-005)

**Checkpoint**: A missing HuggingFace token is reported as a failure of the speaker path, in 32 s

---

## Phase 5: User Story 3 - Also cover the progress and estimate wiring (Priority: P3)

**Goal**: One real run confirms that the fields specs 020/021 added actually arrive from the real engine

### Tests for User Story 3

- [x] T020 [P] [US3] `tests/test_verify_quick.py`: artifacts present but no update naming the sampled file is a failure (INV-3); no update carrying a finish time is a failure

### Implementation for User Story 3

- [x] T021 [US3] Collect every snapshot the worker emits and require at least one naming the sampled media and at least one with `eta_epoch > 0` (FR-007)
- [x] T022 [US3] Print the counts in the verdict block (`N del archivo, M con hora estimada`) so a pass states what it proved

**Checkpoint**: A regression in the 020/021 wiring fails the check even if the transcript is produced

---

## Phase 6: Documentation & Polish

- [x] T023 [P] Rewrite the `## Verificación rápida` block in `CLAUDE.md`: the command that runs, the sandbox guarantee, measured times, what a failure means
- [x] T024 [P] Update the `README.md` verification lines (sample + sandbox, fast variant, full mode with `--force`)
- [x] T025 [P] Write `specs/022-usable-quick-verification/quickstart.md`: measured times, a passing run, how to read each failure
- [x] T026 Run the whole suite headless (`QT_QPA_PLATFORM=offscreen`, `PYTHONIOENCODING=utf-8`) — 170 tests green
- [x] T027 Manual acceptance: `--quick --no-speakers --seconds 20` (22 s, exit 0) and `--quick --seconds 20` (32 s, exit 0, 1 speaker); sandbox gone; real queue, destination and speed history untouched

---

## Phase 7: Remediation from `/speckit-analyze` (see analyze.md)

- [x] T028 [G1] Count a speaker **map** (`{SPEAKER_00: …}`), the shape the engine really writes: the first run failed a healthy pipeline ("se pidieron hablantes y el resultado no trae ninguno") because only lists were counted — covered by `test_speaker_map_is_counted`
- [x] T029 [G2] Release the queue lock on shutdown (`TranscriptionWorker.shutdown(wait=)` joins the thread and closes `worker.lock` only if it really stopped) so the sandbox can be deleted; the first passing run left the folder behind

---

## Dependencies

- Phase 2 (T002–T005) blocks everything: the functions and the sandbox are the substrate.
- T010 blocks T011 (no sample, nothing to enqueue); T011 blocks T012, T019, T021.
- T015 depends on T014 (cleanup exists) and on the worker change.
- Phase 6 documentation depends on the measured times from T027.
- T028/T029 came out of the first real runs (analyze.md) and are already folded in.

## Notes

- `[P]` tasks touch different files and can run in parallel.
- No Transcriptor change: the engine is only invoked, never reconfigured (V-7).
- Only T027 needs a real engine run; everything else is offline.
