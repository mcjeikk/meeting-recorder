# Tasks: A Mac installer that records and transcribes

**Input**: [spec.md](./spec.md), [plan.md](./plan.md)

## Phase 1 — Platform layer (no behaviour change on Windows)

- [x] **T001** `app/core/platform_paths.py`: `config_dir()`, `local_dir()`, `venv_python(root)`, `engine_dir()`; Windows values identical to today. Tests in `tests/test_platform_paths.py`. (FR-018, FR-021)
- [x] **T002** Route `config._config_path`, `output_path` local base, `integration.transcripts_base`, `integration.transcriptor_paths`, `config._is_complete` through it; engine dir first candidate on macOS. (FR-015, FR-018)
- [x] **T003** `worker.py` on POSIX: `start_new_session`, priority via `apply_priority_to_pid`, keep-awake via `caffeinate -i -w`, single-worker lock via `fcntl`. (FR-017)
- [x] **T004** `main.py` on macOS: single instance via `QLockFile`, app name; `ffmpeg.py`: `h264_videotoolbox` candidate on macOS.

## Phase 2 — macOS capture (US1)

- [x] **T005** `app/capture/audio_gaps.py` (pure) + `tests/test_audio_gaps.py`: silence before first buffer, between buffers, until stop; planar/interleaved float → int16. (FR-005)
- [x] **T006** `app/capture/frame_pipe.py`: constant-rate BGRA writer to ffmpeg, resize on size change. Frames are counted against the clock (repeat the last one when ffmpeg lags) — `tests/test_frame_pipe.py`.
- [x] **T007** `app/capture/mac_sck.py`: shareable content (displays, windows), `SCKVideoCapture`, `SCKSystemAudioCapture`, one-shot preview frame, own-app exclusion. (FR-005, FR-006, FR-010)
- [x] **T008** `app/capture/sources.py` facade; `orchestrator.py` and `main_window.py` use it; `monitor.py` skips the loopback meter off Windows. (FR-005, FR-008, FR-012)
- [x] **T009** `app/core/mac_permissions.py` + pre-record check in the window: name, purpose, open Settings, restart hint. (FR-007)

## Phase 3 — macOS UI parity (US1)

- [x] **T010** `app/ui/hotkeys_mac.py` (Carbon, ⌃⌥R/P/M) wired in place of the Win32 filter on macOS. (FR-009)
- [x] **T011** Hotplug polling on macOS feeding `hotplug_action` (`app/ui/mac_devices.py`, 3 s timer). (FR-011)
- [x] **T012** sharingType none + exclusion flag passed to captures — landed in `app/ui/capture_affinity.py` (`_apply_macos`) instead of a separate `mac_window.py`. (FR-010)
- [x] **T013** Hide on macOS: mic-usage label, auto-mute, Bluetooth loopback hint; Mac shortcut labels in the UI. (FR-012)

## Phase 4 — Engine on first use (US2)

- [x] **T014** `transcriptor/requirements.lock.macos.txt` (14+, validated pins) and `requirements.lock.macos13.txt` (13, unverified), resolved with `uv pip compile --python-platform aarch64-apple-darwin`.
- [x] **T015** `app/transcription/engine_setup.py` + `tests/test_engine_setup.py`: steps, `.venv.partial` → `.venv` only after verification, state file, lock-hash versioning, interruption/retry, suspend while recording. (FR-013, FR-014)
- [x] **T016** `app/transcription/hf_token.py` + `tests/test_hf_token.py`: check (whoami + gated file), store (mode 600, `.env`), mask. (FR-016)
- [x] **T017** `app/ui/engine_dialogs.py` + window wiring: consent with size/internet/disk, progress, pending jobs start when ready; token dialog in transcription options. (FR-013, FR-016)

## Phase 5 — Packaging and CI (US3)

- [x] **T018** `packaging/macos/`: launcher with `--self-check`, PyInstaller spec (Info.plist, data, uv, excludes), `build.sh` (ad-hoc sign, dmg with Applications link and LEEME). (FR-001, FR-003, FR-004)
- [x] **T019** `tools/mac_engine_check.py` (real setup via `engine_setup` + `say` transcript) and `tools/mac_capture_check.py` (permissions, displays/windows, encoder, 3 s screen + system audio).
- [x] **T020** `.github/workflows/macos.yml`: app job (tests, capture probe, real clips, build, size, artifact), engine job, release on tags. (FR-019, FR-020)
- [x] **T021** `requirements.txt` macOS markers; `test_requirements_declared.py` mapping; Windows-only tests skipped elsewhere.
- [x] **T022** CI green on `macos-14`; installer downloadable. (SC-005, SC-007)

## Phase 6 — Windows intact, docs, acceptance

- [x] **T023** Windows: `run_all_tests.ps1`, `verify_pipeline.py`, `verify_transcription.py --quick` green on this machine. (FR-021, SC-006)
- [x] **T024** README (Mac section: download, first open, permissions, engine, token, gaps), CLAUDE.md (macOS traps), LEEME.
- [x] **T025** `/speckit.analyze` pass; evidence recorded here.
- [ ] **T026** Acceptance on the user's Apple Silicon Mac (SC-001..SC-004) — needs the user; checklist handed over.

## Evidence (23-oct-2026)

CI run [40036144949](https://github.com/mcjeikk/meeting-recorder/actions/runs/40036144949), `macos-14-arm64` (macOS 14.8.9):

| Check | Result |
|---|---|
| App tests | 310 OK (Windows-only ones skipped) |
| Capture probe | displays/windows listed, frame grabbed, 3 s screen + system audio written |
| `verify_pipeline.py` (real clips) | B screen + system audio: 1 video, 1 audio · E pause/resume: 7.0 s for ~7 s active, pause excluded 2.7 s |
| `.dmg` | 86.8 MB (< 500 MB, SC-007), ad-hoc signed, `--self-check` ok, no `.env` inside |
| Engine job | `uv` install from `requirements.lock.macos.txt` in ~36 s, `transcribe.py --help`, worker transcript of a `say` clip → txt/srt/json |

Windows (this machine): `run_all_tests.ps1` 310 + 10 OK; `verify_pipeline.py` TODO OK; `verify_transcription.py --quick --no-speakers --seconds 20` OK in 34 s.

Bugs the Mac CI found on the way (all fixed, with tests where pure):

- Offscreen Qt + `winId()` → segfault in `capture_affinity` (guard on `platformName() == "cocoa"`).
- Engine copy skipped `pipeline/output.py` (global `output*` ignore) → root-only ignore + regression test.
- Constant-rate writer reset its clock when ffmpeg lagged → video shorter than the audio (5.1 s for 7 s). Now counts frames against the clock.
- A child process launched by a process that already used ScreenCaptureKit gets every stream cut ("application connection being interrupted"). Only affected the check tool; it now runs `verify_pipeline` in-process and CI runs it as its own step.
- Pre-existing `NameError: OK` in `main_window._import_media_paths` (Windows too).

## Analyze (T025)

- Every FR maps to at least one task; FR-019/FR-020 live in the workflow triggers (`push: main`, `tags: v*`).
- **Covered only by the user (T026):** SC-001 (10 min without terminal), SC-002 (100 ms sync with microphone — CI runners have no microphone), SC-003 (engine with speakers on a home connection; CI validates without speakers since it has no HF token), SC-004 (network cut mid-setup; logic covered by `test_engine_setup` interruption cases).
- **Known gap:** `requirements.lock.macos13.txt` is unverified in CI (GitHub's macOS 13 runners are Intel). On macOS 13 the engine uses that lock; a failure would surface in the setup log with a retry button.
