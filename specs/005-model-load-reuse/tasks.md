# Tasks: Model-Load Reuse (005)

**Status**: Documentation complete; **code deferred** (see [deferral.md](./deferral.md))

## Phase 1: Artifacts

- [X] T001 Write `spec.md`
- [X] T002 Write `validation.md`
- [X] T003 Write `plan.md` + `research.md` + `quickstart.md`
- [X] T004 Write `deferral.md` with explicit skip rationale
- [X] T005 Update `.specify/feature.json` → `specs/005-model-load-reuse`
- [X] T006 Cross-link from `specs/002-transcription-speed-presets/plan.md` Phase 2 to 005

## Phase 2: Code (DEFERRED)

- [ ] T007 Design IPC contract for warm sibling worker
- [ ] T008 Implement Transcriptor warm worker (opt-in)
- [ ] T009 Recorder prefer-warm-else-cold + RAW suspend
- [ ] T010 Cold vs warm measurement recorded in quickstart

> Do **not** implement T007–T010 in this audit pass.
