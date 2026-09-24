# Tasks: Someone who clones both repositories can record and transcribe

**Input**: [spec.md](./spec.md)

**Note on process**: no separate `plan.md`. The code change is one resolver in `config.py` used in two places; the rest is publishing and documentation, and the plan is the acceptance run itself.

## Phase 1 — Tests first

- [x] **T001** `tests/test_transcriptor_discovery.py`: the `git clone` folder name, the development name and the legacy location are found; a folder without the CLI is not. (FR-002)
- [x] **T002** Same file: a valid saved path wins; an empty or stale one is rediscovered; with nothing found the saved path is kept. (FR-003, FR-004)
- [x] **T003** Same file: loading a configuration saved with an empty path heals it. (FR-003)

## Phase 2 — Implementation

- [x] **T004** `app/core/config.py`: `default_transcriptor_dir` also looks for `meeting-transcriber`; new `resolve_transcriptor_dir`; `AppConfig.load` applies it. (FR-002, FR-003)
- [x] **T005** `app/transcription/worker.py`: resolve the path at each job and launch the CLI from the resolved path. (FR-003, FR-005)
- [x] **T006** `verify_transcription.py`: actionable messages for no recordings and no Transcriptor. (FR-006)

## Phase 3 — Publishing and documentation

- [ ] **T007** Transcriptor: commit the pending work (multi-file CLI, exclusive speakers, model reuse, WAV reuse, thread cap, pyannote 4.0.7, its tests) and push. (FR-001)
- [ ] **T008** Transcriptor README: usage from the Recorder, measured speed, when ffmpeg is needed, running its tests. (FR-007)
- [ ] **T009** Recorder README: one ordered installation path for recording and transcription. (FR-007)
- [ ] **T010** Recorder: full suite green; commit and push.

## Phase 4 — Acceptance (the run that proves it)

- [ ] **T011** In a clean folder, with `APPDATA` pointing to an empty folder, clone both repositories from GitHub, install each as its README says, and run both test suites. (SC-004)
- [ ] **T012** Fresh Transcriptor: two files in one call produce two transcripts. (SC-002)
- [ ] **T013** Fresh Recorder, no configuration: `verify_transcription.py --quick` on a real recording finds the fresh Transcriptor on its own and returns a transcript with speakers. (SC-001, SC-003)
