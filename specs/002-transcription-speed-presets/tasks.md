# Tasks: Transcription Speed Presets

**Input**: Design documents from `/specs/002-transcription-speed-presets/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/, quickstart.md

**Tests**: Spec does not mandate TDD. Include focused unit tests for preset→CLI mapping (high value, pure functions). Headless smoke + manual quickstart for UI/queue. Phase 2 is documentation-only until explicitly implemented.

**Organization**: Tasks grouped by user story for independent delivery. Phase 1 of the product = US1–US3; US4 is Phase 2 planning/docs (no Recorder code required to mark “plan ready”).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: US1…US4 from spec.md
- Include exact file paths

## Path Conventions

- Recorder: `app/core/config.py`, `app/transcription/*`, `app/ui/main_window.py`
- Sibling Transcriptor: only for Phase 2 (US4) exploration — do not fuse venvs

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm touch points; no behavior change yet

- [X] T001 [P] Inventory enqueue → worker → `build_command` path in `app/transcription/worker.py`, `app/transcription/jobs.py`, `app/transcription/integration.py` (note where `--threads` / `--no-diarize` are appended today)
- [X] T002 [P] Inventory UI transcription controls and `_save_config` / `_apply_saved_config` in `app/ui/main_window.py` and `AppConfig` fields in `app/core/config.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Single source of truth for preset IDs and CLI mapping — required before UI and queue work

**⚠️ CRITICAL**: User story implementation waits on this phase

- [X] T003 Create `app/transcription/presets.py` with ids `rapido|equilibrado|maxima_calidad`, Spanish labels, hints, and `to_cli_args(preset_id) -> list[str]` per `contracts/cli-preset-mapping.md` / research.md (Rápido: large-v3-turbo/1/--no-diarize; Equilibrado: large-v3-turbo/5; Máxima: large-v3/5 — do **not** use medium for Rápido)
- [X] T004 Add `normalize_preset(value) -> str` in `app/transcription/presets.py` that maps unknown/empty to `equilibrado` (FR-012)
- [X] T005 [P] Add unit tests for mapping + normalize in `tests/test_transcription_presets.py` (create `tests/` if missing; use pytest already available or `unittest`)
- [X] T006 Extend `AppConfig` in `app/core/config.py` with `transcription_preset: str = "equilibrado"` (load/save via existing JSON path)

**Checkpoint**: Mapping module + config field ready; stories can proceed

---

## Phase 3: User Story 1 - Choose a speed/quality preset before transcribing (Priority: P1) 🎯 MVP

**Goal**: User can select Rápido / Equilibrado / Máxima calidad; preference persists; jobs run with the mapped CLI flags

**Independent Test**: Select each preset, restart app (selection restored); enqueue/finish a short job and confirm queue JSON + log argv match the mapping (quickstart steps 2–8)

### Implementation for User Story 1

- [X] T007 [US1] Extend `TranscriptionJob` in `app/transcription/jobs.py` with `preset`, `model`, `beam_size` fields; keep `no_diarize`; default missing fields to equilibrado on load for old JSON
- [X] T008 [US1] Update `JobStore.enqueue` / `TranscriptionWorker.enqueue` signatures in `app/transcription/jobs.py` and `app/transcription/worker.py` to accept preset id, snapshot mapping onto the job at enqueue time
- [X] T009 [US1] In `app/transcription/worker.py` `_execute`, append preset CLI args from job fields via `presets.to_cli_args` (or denormalized fields); ensure `--no-diarize` appears once when `job.no_diarize`; keep `--threads` behavior
- [X] T010 [US1] Wire all Recorder enqueue call sites (e.g. finish-recording path in `app/ui/main_window.py`) to pass `self._config.transcription_preset` (normalized)
- [X] T011 [US1] Add preset selector control in `app/ui/main_window.py` (combo or exclusive buttons) with three Spanish labels per `contracts/ui-transcription-presets.md`
- [X] T012 [US1] Persist preset on change and restore in `_apply_saved_config` / `_save_config` in `app/ui/main_window.py` using `AppConfig.transcription_preset`

**Checkpoint**: MVP — presets selectable, persisted, and applied to new jobs

---

## Phase 4: User Story 2 - Understand the trade-off before starting a job (Priority: P1)

**Goal**: Dynamic hint text explains speed vs speakers for the selected preset

**Independent Test**: Change presets and verify hint updates (Rápido = no speakers; others = speakers; Máxima slower/heavier)

### Implementation for User Story 2

- [X] T013 [US2] Add hint label next to the preset control in `app/ui/main_window.py` bound to `presets` hint strings; update on selection change
- [X] T014 [US2] Align checkbox / banner copy in `app/ui/main_window.py` so it does not contradict the active preset (e.g. avoid always claiming “con hablantes” when Rápido is selected)

**Checkpoint**: User sees accurate trade-off before waiting on a job

---

## Phase 5: User Story 3 - Preset applies to queued/retried jobs; recording still wins (Priority: P2)

**Goal**: Job snapshot immutable after enqueue; retry keeps preset; Recording Always Wins unchanged

**Independent Test**: Change UI preset while a job is queued → JSON unchanged; retry keeps fields; start recording mid-job → suspend/yield as today

### Implementation for User Story 3

- [X] T015 [US3] Ensure `retry` in `app/transcription/jobs.py` / `app/transcription/worker.py` preserves `preset`/`model`/`beam_size`/`no_diarize` (except intentional degraded `no_diarize=True` override)
- [X] T016 [US3] Confirm degraded-diarization path still forces `--no-diarize` even for Equilibrado/Máxima in `app/transcription/worker.py` (research R4)
- [X] T017 [US3] Audit recording gates: preset UI may stay enabled; worker still skips/suspends when `is_recording()` — no changes that start jobs during capture (`app/transcription/worker.py`, `app/ui/main_window.py`)
- [X] T018 [US3] Optional: include preset id in UI stage/status emission snapshot text in `app/transcription/worker.py` / banner handlers for easier debugging (nice-to-have; skip if noisy)

**Checkpoint**: Queue semantics + Recording Always Wins hold with presets

---

## Phase 6: User Story 4 - Plan model-load reuse (Phase 2) (Priority: P3)

**Goal**: Constitution-compliant reuse approach documented; no fused venv; Phase 1 not blocked

**Independent Test**: Plan section in feature docs describes ≥1 sibling-side approach and measurement method; no Recorder torch import proposed

### Implementation for User Story 4

- [X] T019 [P] [US4] Expand Phase 2 section in `specs/002-transcription-speed-presets/plan.md` (or add `specs/002-transcription-speed-presets/phase2-model-reuse.md`) with chosen approach options, reject fused-venv, and cold-vs-warm measurement steps from quickstart
- [X] T020 [US4] Explicitly mark Phase 2 code work out of scope for `/speckit-implement` of Phase 1 (note in tasks/plan); do **not** implement Transcriptor daemon unless user confirms Phase 2 implement

> **Phase 2 code deferred**: no Transcriptor daemon / model-cache process in this implement pass. Docs only (T019–T020).

**Checkpoint**: Phase 2 is planned and clearly deferred

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Validation and scope guardrails

- [X] T021 [P] Run unit tests: `.\.venv\Scripts\python.exe -m pytest tests/test_transcription_presets.py -q` (or unittest equivalent)
- [X] T022 Run headless smoke: `$env:QT_QPA_PLATFORM='offscreen'; $env:PYTHONIOENCODING='utf-8'; .\.venv\Scripts\python.exe smoke_test.py`
- [ ] T023 Execute manual quickstart Phase 1 steps in `specs/002-transcription-speed-presets/quickstart.md` (ordering SC-002 when feasible) — **pending user**: see quickstart.md; not automated in this pass
- [X] T024 [P] Scope check: no venv fusion, no cloud upload, no LLM, no scheduled-task worker; Transcriptor changes only if Phase 2 explicitly started

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: start immediately
- **Foundational (Phase 2)**: after Setup — **BLOCKS** US1–US3
- **US1 (Phase 3)**: after Foundational — **MVP**
- **US2 (Phase 4)**: after T011 (needs selector); can finish right after US1 UI
- **US3 (Phase 5)**: after T007–T009 (job fields + worker)
- **US4 (Phase 6)**: independent docs; can run parallel anytime after research exists
- **Polish (Phase 7)**: after desired stories (ideally US1–US3)

### User Story Dependencies

- **US1**: Foundation → delivers end-to-end preset → CLI
- **US2**: Needs US1 selector (T011); hint-only otherwise
- **US3**: Needs job snapshot from US1
- **US4**: Docs only; parallel

### Parallel Opportunities

- T001 ∥ T002
- T005 ∥ T006 (after T003–T004)
- T019 ∥ any Phase 3–5 work
- T021 ∥ T024 after code complete

---

## Implementation Strategy

### MVP (recommended first ship)

1. Complete Phase 1–2 (presets module + config)
2. Complete US1 (T007–T012)
3. Add US2 hints (T013–T014) in the same UI pass if cheap
4. Stop for user validation before US3 polish / Phase 2 code

### Incremental delivery

1. Mapping + tests green
2. Queue/worker apply flags (even before fancy UI: config.json editable)
3. UI selector + persistence
4. Hints + retry/recording audits
5. Phase 2 only on explicit confirm

### Suggested MVP task slice

T001–T012 (+ T013–T014 if same PR)

---

## Notes

- Degraded retry `no_diarize` overrides preset diarize-on (R4).
- Old queue files without preset fields → equilibrado defaults.
- Do not implement code for US4/Phase 2 model daemon in the first implement pass unless the user asks.
