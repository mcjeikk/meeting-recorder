# Tasks: Device Hotplug Auto-Refresh

**Input**: Design documents from `/specs/004-device-hotplug/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel
- **[Story]**: [US1]/[US2]/[US3]

## Phase 1: Setup

- [x] T001 Create `app/ui/device_watcher.py` skeleton (Windows constants + no-op non-Windows)
- [x] T002 [P] Add `tests/test_device_hotplug.py` scaffold importing watcher + policy helpers

## Phase 2: Foundational

- [x] T003 Implement `DeviceChangeWatcher` (`WM_DEVICECHANGE` filter → callback) in `app/ui/device_watcher.py`
- [x] T004 [P] Unit-test watcher invokes callback for arrival/removal/nodes_changed (ctypes MSG mock)

## Phase 3: User Story 1 — Auto list update idle (P1) — MVP

**Goal**: Idle hotplug updates mic combo without Actualizar

- [x] T005 [US1] Extend `_refresh_mics(..., auto=False)` deep-reinit when `(manual or auto) and not recording` in `app/ui/main_window.py`
- [x] T006 [US1] Wire watcher + ~800 ms debounce `QTimer` → `_refresh_mics(auto=True)` when idle
- [x] T007 [US1] Install/remove native filter with app lifecycle (alongside hotkeys)
- [x] T008 [P] [US1] Test/assert idle path requests deep refresh (mock recording=False)

## Phase 4: User Story 3 — Recording safety (P1)

**Goal**: No PortAudio reinit / no stop during recording; pending refresh on idle

- [x] T009 [US3] On debounce while recording: set pending flag only
- [x] T010 [US3] After recording stops, if pending → auto deep refresh once
- [x] T011 [P] [US3] Tests for pending flag + no refresh=True while recording

## Phase 5: User Story 2 — Selection + debounce polish (P2)

- [x] T012 [US2] Ensure auto path reuses selection restore + status messages (incl. lost device)
- [x] T013 [US2] Optional ~2 s follow-up auto refresh after idle auto (cancel if recording)
- [x] T014 [P] [US2] Quickstatus/doc note in quickstart already covered — mark manual checklist ready

## Phase 6: Polish

- [x] T015 Run `python -m unittest tests.test_device_hotplug tests.test_list_microphones_refresh -q` and fix failures

## Dependencies

- T001 → T003 → T006/T007
- T005 before T006
- US3 (T009–T011) after US1 wiring
- US2 polish after US1/US3

## Parallel examples

```text
T002 || T001
T004 || T005
T008 || T011
```

## Implementation strategy

MVP = Phases 1–4 (US1+US3). Phase 5 follow-up timer is small — include in same ship if time allows.
