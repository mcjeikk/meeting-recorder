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

- [x] **T007** Transcriptor: commit the pending work (multi-file CLI, exclusive speakers, model reuse, WAV reuse, thread cap, pyannote 4.0.7, its tests) and push. (FR-001) — `2d6881e`
- [x] **T008** Transcriptor README: usage from the Recorder, measured speed, when ffmpeg is needed, running its tests. (FR-007) — `80c9560`
- [x] **T009** Recorder README: one ordered installation path for recording and transcription. (FR-007)
- [x] **T010** Recorder: full suite green; commit and push. — `e580038`

## Phase 4 — Acceptance (the run that proves it)

- [x] **T011** In a clean folder whose path contains a space, clone both repositories from GitHub and install each exactly as its README says. Transcriptor: 10 tests OK on torch 2.14.0+cpu / torchaudio 2.11.0 / ctranslate2 4.8.2 — newer than the author's validated environment. **Recorder: 206 of 243 tests ran, 9 import errors: `No module named 'psutil'`; the app did not open.** (SC-004) → T014–T017
- [x] **T012** Fresh Transcriptor: `uno.wav dos.wav` in one call → "Archivos a procesar: 2", both "Audio ya en WAV 16 kHz; se omite reconversión", both with speakers, exit 0, two transcripts. (SC-002)
- [ ] **T013** Fresh Recorder, no configuration: `verify_transcription.py --quick` on a real recording finds the fresh Transcriptor on its own and returns a transcript with speakers. (SC-001, SC-003)

## Phase 5 — What the acceptance run caught

- [x] **T014** `requirements.txt`: declare `psutil` (worker: suspend/resume, priority, re-adoption) and `opencv-python` (imported directly by the capture code). (FR-008)
- [x] **T015** `tests/test_requirements_declared.py`: every third-party import under `app/` must map to a declared distribution; verified to fail against the old `requirements.txt`. (FR-008)
- [x] **T016** `smoke_test.py`: load the whole app (fails if a dependency is missing) and report transcription readiness — Transcriptor path and whether a Hugging Face token is set, never printing it. (FR-009)
- [ ] **T017** Fresh clone updated the way a user would (`git pull` + `pip install -r requirements.txt`): full suite green and `smoke_test.py` OK. (SC-004)
