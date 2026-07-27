# Tasks: Refresh Capture Devices

**Input**: Design documents from `/specs/001-refresh-devices/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/ui-refresh-devices.md, quickstart.md

**Tests**: No automated TDD suite requested in the spec. Validation is manual via [quickstart.md](./quickstart.md) plus existing `smoke_test.py` (headless). Optional light unit coverage only if a pure selection helper is extracted.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- Desktop app under `app/` (see plan.md); primary change surface is `app/ui/main_window.py`
- Reuse only: `app/capture/windows_audio.py`, `app/capture/windows_video.py`, `app/capture/monitor.py`, `app/core/orchestrator.py`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Orient on existing APIs and UI touch points — no new packages, modules, or Transcriptor changes

- [X] T001 [P] Confirm reuse-only APIs for this feature: `list_microphones()` in `app/capture/windows_audio.py`, `AudioMonitor.set_mic` in `app/capture/monitor.py`, and `Recorder.change_mic` in `app/core/orchestrator.py` (no signature/contract changes)
- [X] T002 [P] Map current UI wiring in `app/ui/main_window.py`: `_on_refresh` → `_refresh_sources` only; `_refresh_mics` forces `setCurrentIndex(1)`; `_set_recording_ui` disables `_source_combo` + `_refresh_btn`; mic section has no Actualizar button yet

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared selection/feedback helpers and recording-gate baseline before story UI work

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T003 Add a private helper in `app/ui/main_window.py` (e.g. `_mic_selection_key` / `_restore_mic_selection`) that restores `_mic_combo` by exact `findText` match on device name or `"Sin micrófono"`, and on miss applies safe fallback to `"Sin micrófono"` (data-model + FR-003/FR-007)
- [X] T004 Ensure `_set_recording_ui` in `app/ui/main_window.py` only gates source controls (`_source_combo`, `_refresh_btn`) and never disables `_mic_combo` (C-RECORDING-GATES baseline); leave a clear place to enable the upcoming mic-refresh button while recording

**Checkpoint**: Foundation ready — user story implementation can begin

---

## Phase 3: User Story 1 - Refrescar micrófonos a demanda (Priority: P1) 🎯 MVP

**Goal**: Explicit Actualizar in the Micrófono section repopulates the mic list without restarting the app; idle level meter follows the selected mic after refresh

**Independent Test**: With the app open, connect/disconnect a known mic, press Actualizar in Micrófono, confirm the list updates; select the new device and verify the meter reacts (quickstart Q1)

### Implementation for User Story 1

- [X] T005 [US1] Add a dedicated mic Actualizar control (e.g. `_mic_refresh_btn`, label `🔄 Actualizar`) in the Micrófono row layout in `app/ui/main_window.py`, visually parallel to the source refresh button
- [X] T006 [US1] Wire the mic Actualizar button to a new handler (e.g. `_on_refresh_mics`) in `app/ui/main_window.py` that calls `_refresh_mics`; keep `_on_refresh` limited to `_refresh_sources` + `_update_preview` (C-MIC-REFRESH / R1)
- [X] T007 [US1] Rewrite `_refresh_mics` in `app/ui/main_window.py` to: capture prior selection key → `list_microphones()` → rebuild combo with `"Sin micrófono"` always → restore via T003 helper; handle empty hardware list without crash; do not re-apply `last_mic_name` on manual refresh (R6 — startup still uses `_apply_saved_config`)
- [X] T008 [US1] After `_refresh_mics` finishes, if not recording, reattach the level meter with `self._monitor.set_mic(self._mic_combo.currentData())` in `app/ui/main_window.py` (FR-005 / R3); if recording, do not stop capture or change mic until the user activates another combo item
- [X] T009 [US1] On successful mic refresh, set a brief status on `_status_label` in `app/ui/main_window.py` (e.g. “Micrófonos actualizados”) so FR-008 feedback is visible even when the list looks similar

**Checkpoint**: User Story 1 is independently usable — new/disconnected mics appear after Actualizar; meter works when idle

---

## Phase 4: User Story 2 - Conservar selección y no romper la grabación (Priority: P2)

**Goal**: Refresh keeps the prior mic when still available; during recording, mic refresh/change stay available and video source controls stay locked; hot-swap path remains intact

**Independent Test**: Select a non-default mic, refresh with no hardware change → same selection (Q2). Short recording: refresh mics, pick another → recording continues with new mic audio (Q4)

### Implementation for User Story 2

- [X] T010 [US2] Verify/complete selection preservation in `_refresh_mics` via the T003 helper in `app/ui/main_window.py`: exact name match restores prior mic; when prior name is missing, fallback + set `_status_label` with a short “ya no disponible” message (FR-007, SC-002)
- [X] T011 [US2] Include `_mic_refresh_btn` in recording gates in `_set_recording_ui` in `app/ui/main_window.py`: enabled while recording (same as `_mic_combo`); `_refresh_btn` + `_source_combo` remain disabled (FR-006 / C-RECORDING-GATES)
- [X] T012 [US2] Confirm `_on_mic_activated` in `app/ui/main_window.py` still routes idle → `AudioMonitor.set_mic` and recording → `Recorder.change_mic` with no video side effects (C-MIC-SELECT); no changes to `app/core/orchestrator.py` unless a defect blocks hot-swap
- [X] T013 [US2] Guard `_refresh_mics` / `_on_refresh_mics` in `app/ui/main_window.py` so enumeration exceptions leave the app usable (keep prior or empty safe list + status message; never crash) per contracts error/empty states

**Checkpoint**: User Stories 1 and 2 both work — selection stable; recording survives mic refresh + hot-swap

---

## Phase 5: User Story 3 - Refresco de ventanas/pestañas sigue claro (Priority: P3)

**Goal**: Source Actualizar remains clear and correct (preserve window/screen selection, update preview); does not refresh mics; stays disabled while recording

**Independent Test**: Open a distinct-titled window, Actualizar sources, select it, refresh again → still selected and preview coherent; during recording source controls disabled (Q5)

### Implementation for User Story 3

- [X] T014 [US3] Audit `_refresh_sources` in `app/ui/main_window.py`: keep restore-by-window-title and screen-sentinel (`userData=None` → stay on full screen); no rewrite unless a regression is found (R7 / FR-004)
- [X] T015 [US3] Confirm `_on_refresh` in `app/ui/main_window.py` only calls `_refresh_sources` + `_update_preview` and never `_refresh_mics` (C-SRC-REFRESH non-goal)
- [X] T016 [US3] Confirm source Actualizar (`_refresh_btn`) and `_source_combo` stay disabled for the whole recording session via `_set_recording_ui` in `app/ui/main_window.py` (FR-006)

**Checkpoint**: All three user stories independently satisfy their acceptance scenarios

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validation and scope guardrails across stories

- [X] T017 Run headless smoke: `QT_QPA_PLATFORM=offscreen` + `PYTHONIOENCODING=utf-8` with `.\.venv\Scripts\python.exe smoke_test.py` (quickstart Q6); fix only regressions introduced by this feature
- [ ] T018 Execute manual quickstart scenarios Q1–Q5 in `specs/001-refresh-devices/quickstart.md` against a real Windows session (two mics preferred)
- [X] T019 [P] Spot-check MVP scope in `app/ui/main_window.py` and related capture modules: no hotplug listeners, no mid-recording video source change, no Transcriptor/queue changes

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS** all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational — MVP
- **User Story 2 (Phase 4)**: Depends on Foundational; practically builds on US1 button + `_refresh_mics` path (T005–T009)
- **User Story 3 (Phase 5)**: Depends on Foundational; can run after or parallel to US1/US2 if staffing allows (mostly audit of existing source path)
- **Polish (Phase 6)**: Depends on desired stories complete (ideally all three)

### User Story Dependencies

- **User Story 1 (P1)**: After Phase 2 — delivers mic Actualizar + list refresh + idle monitor reattach
- **User Story 2 (P2)**: After US1 mic-refresh path exists — selection preserve messaging, recording gates for mic button, hot-swap confirmation
- **User Story 3 (P3)**: After Phase 2 — regression/parity on sources; independent of mic button but should not regress US1/US2 gates

### Within Each User Story

- UI control before handler wiring
- Repopulate/restore before monitor reattach
- Idle behavior before recording-gate refinements
- Story complete before moving to next priority when working solo

### Parallel Opportunities

- T001 and T002 (Setup) can run in parallel
- After Phase 2: US3 audit tasks (T014–T016) can proceed in parallel with US1 if careful not to conflict in `main_window.py` (same file → prefer sequential for one implementer)
- T019 can run in parallel with T017/T018 once implementation is done
- No multi-file [P] implementation tasks inside US1–US2 because nearly all edits land in `app/ui/main_window.py`

---

## Parallel Example: User Story 1

```text
# Same-file story — run sequentially for one agent:
Task: "Add mic Actualizar button in app/ui/main_window.py"
Task: "Wire _on_refresh_mics → _refresh_mics in app/ui/main_window.py"
Task: "Rewrite _refresh_mics with restore helper in app/ui/main_window.py"
Task: "Reattach AudioMonitor.set_mic when idle after refresh in app/ui/main_window.py"

# True parallel only across stories/files (e.g. US3 audit notes vs US1), not recommended in one file:
# Prefer finishing US1 MVP before US2 gates in the same module.
```

---

## Parallel Example: User Story 3

```text
# Audit-only tasks in app/ui/main_window.py (read/verify, minimal edits):
Task: "Audit _refresh_sources selection preserve"
Task: "Confirm _on_refresh does not call _refresh_mics"
Task: "Confirm source controls disabled while recording"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL)
3. Complete Phase 3: User Story 1 (T005–T009)
4. **STOP and VALIDATE**: quickstart Q1 (+ empty-list edge if possible)
5. Demo mic Actualizar before continuing

### Incremental Delivery

1. Setup + Foundational → helpers and gate baseline ready
2. US1 → mic list refresh MVP
3. US2 → selection preserve + recording safety
4. US3 → source refresh parity confirmed
5. Polish → smoke + Q1–Q5 + scope check

### Parallel Team Strategy

With multiple developers (limited by single primary file):

1. Team completes Setup + Foundational together
2. Developer A: US1 then US2 in `app/ui/main_window.py`
3. Developer B: US3 audit / quickstart notes (avoid simultaneous edits to the same methods)
4. Integrate and run Phase 6 validation

---

## Notes

- [P] tasks = different files or truly independent checks; most story work shares `app/ui/main_window.py`
- Identity key for mics = exact visible name (not WASAPI index)
- Recording Always Wins: enumeration must not stop or pause an active recording
- Out of MVP: hotplug, mid-recording video source change, Transcriptor changes
- Commit after each task or logical group only when the user requests commits
- Stop at any checkpoint to validate the story independently
