# Tasks: The notice names the phase that is actually running

**Input**: Design documents from `/specs/024-truthful-phase-label/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/phase-labels.md

**Tests**: Included (everything is decidable by replaying log text through a pure parser)

**Organization**: Tasks are grouped by user story.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

- [x] T001 Point `.specify/feature.json` at `specs/024-truthful-phase-label`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Make the phase a value and the label a lookup

**⚠️ CRITICAL**: No user story work until this phase is complete

- [x] T002 Add the phase constants, `PHASE_LABELS`, `label_for_phase()` and `PHASES_WITHOUT_ASR_PERCENT` to `app/transcription/cli_progress.py` (one place for wording, one statement of the percentage rule)
- [x] T003 Return the phase as a fifth field from `parse_plain_chunk`, deriving `stage` from it, keeping the first four fields in order and meaning (C-2, C-4, INV-8, INV-9)

**Checkpoint**: The parser speaks in phases; labels are data

---

## Phase 3: User Story 1 - The notice tells the truth about what is happening (Priority: P1) 🎯 MVP

**Goal**: The label names the running phase, from the engine's own announcements

### Tests for User Story 1

- [x] T004 [P] [US1] `tests/test_cli_progress.py`: the transcription announcement (`- Transcribiendo (modelo …)`) sets the transcribing phase with no percentage present (SC-003, P-4)
- [x] T005 [P] [US1] `tests/test_cli_progress.py`: `Audio ya en WAV` starts no phase, and a preparation label never accompanies a transcription percentage (SC-002, P-3, INV-1)
- [x] T006 [P] [US1] `tests/test_cli_progress.py`: the device line and the speaker count both move to the writing-results phase with an indeterminate percentage (P-6, P-8, INV-2)
- [x] T007 [P] [US1] `tests/test_cli_progress.py`: replaying the real log of a finished job line by line yields prepare → asr → speakers → saving, with no phase re-entered after it ended (SC-001)
- [x] T008 [P] [US1] `tests/test_cli_progress.py`: unknown lines and `OK en …` leave phase, label and percentage untouched (P-11, P-12, INV-3)
- [x] T009 [P] [US1] `tests/test_cli_progress.py`: the diarization-failure warnings move to writing results and keep the `sin hablantes` note (P-9, P-10)

### Implementation for User Story 1

- [x] T010 [US1] Match `- Transcribiendo (modelo` in `parse_plain_chunk` → transcribing phase (FR-001)
- [x] T011 [US1] Stop treating `Audio ya en WAV` as a phase; keep `Convirtiendo audio` as preparation (FR-002, INV-1)
- [x] T012 [US1] Map the device line and the speaker-count line to the writing-results phase; stop relabelling on `cuda` (FR-003, FR-004, FR-008)
- [x] T013 [US1] Keep `Identificando hablantes` as its own phase with an indeterminate percentage (FR-005)

**Checkpoint**: A real run reads preparing → transcribing → identifying speakers → writing results

---

## Phase 4: User Story 2 - The label is text, not logic (Priority: P2)

**Goal**: No progress behavior depends on the words shown to the user

### Tests for User Story 2

- [x] T014 [P] [US2] `tests/test_cli_progress.py`: `PHASES_WITHOUT_ASR_PERCENT` decides applicability, and every phase's label comes from `label_for_phase` (INV-5, INV-6)
- [x] T015 [US2] `tests/test_batch_tracking.py`: the monitor loop still makes the percentage indeterminate during speaker identification, now driven by phase, and the pause label still wins (W-2, W-4)

### Implementation for User Story 2

- [x] T016 [US2] Track the phase in `worker._monitor` and replace the `"hablantes" in nuevo_stage.lower()` test with a phase membership check (FR-006, W-1..W-3)
- [x] T017 [US2] Reset the phase to transcribing when the next file in a batch is promoted (W-5)

**Checkpoint**: Rewording the notice cannot change how the bar behaves

---

## Phase 5: Documentation & Polish

- [x] T018 [P] Add the phase table to `CLAUDE.md` as the reading contract of the engine log (and why `Audio listo…` was wrong)
- [x] T019 [P] Write `specs/024-truthful-phase-label/quickstart.md`: the label sequence to expect, and how to replay a log by hand
- [x] T020 Run the whole suite headless (`QT_QPA_PLATFORM=offscreen`, `PYTHONIOENCODING=utf-8`)
- [x] T021 Acceptance against the real engine: `verify_transcription.py --quick --seconds 20` and confirm the printed sequence contains no `Audio listo…` and ends with the writing-results label

---

## Dependencies

- Phase 2 (T002–T003) blocks everything: the phase value is the substrate.
- T010–T013 are independent edits inside the same function; do them together, they are one rewrite of the matching block.
- T016 depends on T003 (the fifth field) and T013.
- T021 depends on the whole implementation and gives the evidence for the analysis.

## Notes

- `[P]` tasks touch different files or independent test cases and can run in parallel.
- No Transcriptor change (FR-010): this feature only reads more of what it already prints.
- Out of scope: a GPU indicator in the UI, progress inside speaker identification.
