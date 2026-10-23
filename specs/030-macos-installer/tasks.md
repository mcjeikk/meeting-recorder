# Tasks: A Mac installer that records and transcribes

**Input**: [spec.md](./spec.md), [plan.md](./plan.md)

## Phase 1 — Platform layer (no behaviour change on Windows)

- [ ] **T001** `app/core/platform_paths.py`: `config_dir()`, `local_dir()`, `venv_python(root)`, `engine_dir()`; Windows values identical to today. Tests in `tests/test_platform_paths.py`. (FR-018, FR-021)
- [ ] **T002** Route `config._config_path`, `output_path` local base, `integration.transcripts_base`, `integration.transcriptor_paths`, `config._is_complete` through it; engine dir first candidate on macOS. (FR-015, FR-018)
- [ ] **T003** `worker.py` on POSIX: `start_new_session`, priority via `apply_priority_to_pid`, keep-awake via `caffeinate -i -w`, single-worker lock via `fcntl`. (FR-017)
- [ ] **T004** `main.py` on macOS: single instance via `QLockFile`, app name; `ffmpeg.py`: `h264_videotoolbox` candidate on macOS.

## Phase 2 — macOS capture (US1)

- [ ] **T005** `app/capture/audio_gaps.py` (pure) + `tests/test_audio_gaps.py`: silence before first buffer, between buffers, until stop; planar/interleaved float → int16. (FR-005)
- [ ] **T006** `app/capture/frame_pipe.py`: constant-rate BGRA writer to ffmpeg, resize on size change.
- [ ] **T007** `app/capture/mac_sck.py`: shareable content (displays, windows), `SCKVideoCapture`, `SCKSystemAudioCapture`, one-shot preview frame, own-app exclusion. (FR-005, FR-006, FR-010)
- [ ] **T008** `app/capture/sources.py` facade; `orchestrator.py` and `main_window.py` use it; `monitor.py` skips the loopback meter off Windows. (FR-005, FR-008, FR-012)
- [ ] **T009** `app/core/mac_permissions.py` + pre-record check in the window: name, purpose, open Settings, restart hint. (FR-007)

## Phase 3 — macOS UI parity (US1)

- [ ] **T010** `app/ui/hotkeys_mac.py` (Carbon, ⌃⌥R/P/M) wired in place of the Win32 filter on macOS. (FR-009)
- [ ] **T011** Hotplug polling on macOS feeding `hotplug_action`. (FR-011)
- [ ] **T012** `app/ui/mac_window.py` sharingType none + exclusion flag passed to captures. (FR-010)
- [ ] **T013** Hide on macOS: mic-usage label, auto-mute, Bluetooth loopback hint; Mac shortcut labels in the UI. (FR-012)

## Phase 4 — Engine on first use (US2)

- [ ] **T014** `transcriptor/requirements.lock.macos.txt` (14+, validated pins) and `requirements.lock.macos13.txt` (13, unverified), resolved with `uv pip compile --python-platform aarch64-apple-darwin`.
- [ ] **T015** `app/transcription/engine_setup.py` + `tests/test_engine_setup.py`: steps, `.venv.partial` → `.venv` only after verification, state file, lock-hash versioning, interruption/retry, suspend while recording. (FR-013, FR-014)
- [ ] **T016** `app/transcription/hf_token.py` + `tests/test_hf_token.py`: check (whoami + gated file), store (mode 600, `.env`), mask. (FR-016)
- [ ] **T017** `app/ui/engine_dialogs.py` + window wiring: consent with size/internet/disk, progress, pending jobs start when ready; token dialog in transcription options. (FR-013, FR-016)

## Phase 5 — Packaging and CI (US3)

- [ ] **T018** `packaging/macos/`: launcher with `--self-check`, PyInstaller spec (Info.plist, data, uv, excludes), `build_dmg.sh` (ad-hoc sign, dmg with Applications link and LEEME). (FR-001, FR-003, FR-004)
- [ ] **T019** `tools/mac_engine_check.py` (real setup via `engine_setup` + `say` transcript) and `tools/mac_capture_check.py` (3 s screen + system audio).
- [ ] **T020** `.github/workflows/macos.yml`: app job (tests, capture probe, build, size, artifact), engine job, release on tags. (FR-019, FR-020)
- [ ] **T021** `requirements.txt` macOS markers; `test_requirements_declared.py` mapping; Windows-only tests skipped elsewhere.
- [ ] **T022** CI green on `macos-14`; installer downloadable. (SC-005, SC-007)

## Phase 6 — Windows intact, docs, acceptance

- [ ] **T023** Windows: `run_all_tests.ps1`, `verify_pipeline.py`, `verify_transcription.py --quick` green on this machine. (FR-021, SC-006)
- [ ] **T024** README (Mac section: download, first open, permissions, engine, token, gaps), CLAUDE.md (macOS traps), LEEME.
- [ ] **T025** `/speckit.analyze` pass; evidence recorded here.
- [ ] **T026** Acceptance on the user's Apple Silicon Mac (SC-001..SC-004) — needs the user; checklist handed over.
