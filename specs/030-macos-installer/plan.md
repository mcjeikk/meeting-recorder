# Implementation Plan: A Mac installer that records and transcribes

**Branch**: `030-macos-installer` (work lands on `main`) | **Date**: 2026-10-23 | **Spec**: [spec.md](./spec.md)

## Summary

Add macOS backends behind the seams the app already has, ship them as an unsigned `.app` inside a `.dmg` built by GitHub Actions on an Apple Silicon runner, and set up the transcription engine on the user's Mac the first time it is needed.

- **Capture**: ScreenCaptureKit, the roadmap's choice, gives both the screen or a window and the system audio, with no driver. The microphone keeps using the cross-platform `MicCapture` (sounddevice). Frames go to ffmpeg through a pipe at a constant rate, as WGC does on Windows.
- **Platform details**: per-user data folders, venv layout, process priority, keeping the Mac awake, the single-instance lock, global shortcuts, hiding the app's own window, device hotplug, and permissions. Each gets a macOS branch; Windows branches stay byte-for-byte where they are.
- **Engine on first use**: the app bundles the Transcriptor's sources, two macOS locks and a pinned `uv` binary. With the user's consent it installs Python 3.11 and the locked packages into its application-data folder. Verification decides success; only then is the environment moved into place, so a half-installed engine can never be picked.
- **Hugging Face token**: entered, checked and stored by the app.
- **CI**: builds the installer, runs the suite on macOS, proves the engine installs and transcribes on Apple Silicon, tries a real ScreenCaptureKit capture, and publishes the `.dmg` on tagged releases.

## Technical Context

**Language/Version**: Python 3.11 for both parts, as on Windows.

**Primary Dependencies (new, macOS only, via environment markers)**:
- `pyobjc-framework-ScreenCaptureKit`, `-AVFoundation`, `-Quartz`, `-Cocoa` and `-CoreMedia`.
- `pyinstaller`, for the build only.
- `uv` 0.13.5, pinned and bundled as a binary. It installs a managed Python 3.11 and the locked packages without any Python on the user's Mac.

**Storage**: `~/Library/Application Support/MeetingRecorder/` takes the place of both `%APPDATA%\MeetingRecorder` and `%LOCALAPPDATA%\MeetingRecorder`. It holds:
- `config.json`
- `transcripts/` (queue, logs, work files)
- `recsess_*` (recording sessions)
- `engine/` (the Transcriptor, its `.venv`, its `.env` with the token, and its setup log)

The uv download cache lives in `~/Library/Caches/MeetingRecorder/uv`, so an interrupted setup resumes its downloads.

**Testing**:
- **Windows (this machine)**: the full suites, plus new platform-neutral unit tests for paths, venv layout, lock selection, the setup state machine, token storage, the audio gap-filling arithmetic and engine versioning.
- **macOS CI (`macos-14`, arm64)**: the same suite; a real engine install with the 14+ lock; a transcription of speech synthesised with `say`, without speakers (with speakers too if an `HF_TOKEN` secret exists); a best-effort ScreenCaptureKit capture; the build plus a size check.
- **The user's Mac**: real capture, permissions and the end-to-end acceptance. Nothing hosted can grant screen and microphone permissions the way a person does.

**Target Platform**: macOS 13+ on Apple Silicon for recording.
- **Engine on macOS 14+**: uses the same package versions validated on Windows (resolved for `macosx_14_0_arm64`).
- **Engine on macOS 13**: onnxruntime 1.26.0, which faster-whisper 1.2.1 requires at that version, has no macOS 13 wheel. That case gets its own lock (onnxruntime 1.23.2, torch 2.11.0, ctranslate2 4.8.3). It is labelled unverified, because GitHub offers no Apple Silicon runner on macOS 13.

**Constraints**:
- Windows behaviour unchanged (FR-021).
- No Apple Developer account: ad-hoc signature only.
- The installer must stay under 500 MB.

## Constitution Check (1.1.0)

- **I. Recording Always Wins — PASS.** Transcription keeps suspending for recordings. Engine setup is a background subprocess and is suspended the same way while recording.
- **II. Privacy Is Local — PASS.** Capture and transcription run on the Mac. The only network use is downloading packages and models, as on Windows today, plus checking the token against Hugging Face. The token lives in the engine folder with mode 600 and never in the bundle or the repository.
- **III. Transcription stays a separate subprocess — PASS.** The app never imports the engine; it runs the engine's own `.venv/bin/python` with the same command line.
- **IV. Robust paths and processes — PASS.**
  - Argument lists everywhere.
  - The application-data folder is not synced.
  - A setup runs in `.venv.partial` and is renamed into place only after the imports are verified.
- **V. Simplicity — PASS.** The design reuses the seams that already exist (capture classes, the frame-to-ffmpeg pipe, the subprocess plus queue) and adds no daemon or helper app. The amendment that makes macOS supported is 1.1.0.

## Design decisions

1. **ScreenCaptureKit for screen, window and system audio.**
   - ffmpeg's `avfoundation` cannot capture one window or the system audio, and its screen input is deprecated.
   - Virtual audio drivers such as BlackHole are excluded by FR-006.
   - ScreenCaptureKit exists since macOS 12.3, and its audio since 13: exactly the spec's floor.
   - Video and system audio are two independent streams, mirroring the Windows split (`VideoCapture` and `SystemAudioCapture`), so the orchestrator, pause and resume, segments and muxing stay unchanged.
2. **Frames at a constant rate through a pipe.** This is the WGC pattern: keep the latest BGRA frame and write it to ffmpeg at a constant `fps`, duplicating it when the screen is static. The shared writer goes in a new `frame_pipe.py` used only by macOS, so the Windows classes are not touched. On Retina displays the capture size is the pixel size, capped at 2560 px on the long side to keep files and CPU reasonable.
3. **System-audio track continuity from timestamps.** ScreenCaptureKit may deliver no buffers while nothing sounds; on Windows the same problem needed a keep-alive. Each buffer carries a host-clock timestamp, so silence is written for every gap: before the first buffer, between buffers, and up to the stop. The WAV then lasts exactly as long as the recording. This arithmetic lives in a pure function and is unit-tested on Windows.
4. **Encoder**: `h264_videotoolbox` first on macOS, with `libx264` as the fallback, both through the existing `detect_h264_encoder` probe.
5. **Permissions before recording.**
   - Screen recording, which also covers system audio, is checked with `CGPreflightScreenCaptureAccess` and requested with `CGRequestScreenCaptureAccess`.
   - The microphone is checked with `AVCaptureDevice.authorizationStatusForMediaType_`, and only if one is selected.
   - When one is missing, a dialog names it, says what it is for, opens the exact Settings pane (`x-apple.systempreferences:` URLs) and says a restart may be needed. No recording starts without it.
6. **Hiding its own window**: excluding the app from the ScreenCaptureKit content filter is what macOS honours for screen capture. `NSWindow.sharingType = none` is set as well, for other recorders.
7. **Global shortcuts on Mac**: Carbon `RegisterEventHotKey` via `ctypes`. It needs no Accessibility permission, unlike event taps. The defaults are ⌃⌥R, ⌃⌥P and ⌃⌥M (spec assumption).
8. **Hotplug on Mac**: poll the AVFoundation audio-device list every 3 s. It does not reinitialise PortAudio, so it never cuts a stream; when the set of names changes, the existing `hotplug_action` decides.
9. **Hidden on Mac (FR-012)**:
   - "which apps are using the microphone" and the auto-mute that depends on it (it reads a Windows registry key);
   - the Bluetooth loopback hint;
   - the idle system-audio meter, since system level is shown only while recording.

   These gaps are documented in the README.
10. **Engine setup** (`app/transcription/engine_setup.py`). It is a small state machine (`absent → installing → ready | failed`) whose state is written to `engine/state.json`. The steps:
    1. Copy the bundled Transcriptor sources into `engine/transcriptor/`; this step is idempotent.
    2. `uv python install 3.11`, into `engine/python`.
    3. `uv venv .venv.partial`.
    4. `uv pip install -r <lock for this macOS>`.
    5. Verify the imports.
    6. Rename `.venv.partial` to `.venv` and write `state.json` as ready, with the lock's hash.

    Each step is a subprocess with its output appended to `engine/setup.log`, and is suspended while recording. A new app version with a different lock hash triggers a reinstall; the old engine keeps working until the new one is verified. On macOS the engine folder is the first candidate in `_transcriptor_candidates`, and "complete" means `.venv/bin/python` plus `transcribe.py`.
11. **Consent**: when a job is queued on Mac and the engine is not ready, the queue keeps it pending. The window shows "Instalar motor de transcripción", with size, internet need and disk space, and the user decides. Nothing downloads without that click (FR-013).
12. **Token**: a dialog in the transcription options, Mac only, to respect FR-021.
    - **Check**: `whoami-v2` validates the token; fetching `config.yaml` of `pyannote/speaker-diarization-community-1` proves the model terms were accepted (403 means not accepted).
    - **Storage**: written as `HUGGINGFACE_TOKEN=…` into `engine/transcriptor/.env` with mode 600. That is where the CLI already reads it.
    - **Display**: masked as `hf_…abcd`.
13. **Packaging**:
    - **Bundle**: PyInstaller in `--windowed` mode builds `Grabador de Reuniones.app`, bundle id `com.mcjeikk.meetingrecorder`.
    - **Info.plist**: `NSMicrophoneUsageDescription`, `NSScreenCaptureUsageDescription`, `LSMinimumSystemVersion=13.0`, `NSHighResolutionCapable`.
    - **Contents**: the Transcriptor sources, the macOS locks and `uv` as data; unused Qt modules excluded.
    - **Signature**: ad-hoc (`codesign --force --deep -s -`).
    - **Image**: a `.dmg` (UDZO) containing the app, an `Applications` link and `LEEME - Primera vez.txt` (opening an unsigned app on current macOS, permissions, updates).
14. **CI** (`.github/workflows/macos.yml`, `macos-14` arm64): runs on push to `main`, tags `v*` and manual dispatch. Jobs:
    - **app**: tests, a capture probe that is allowed to fail and reports, the build, the size check, and the artifact.
    - **engine**: a real setup through the same code path, the Transcriptor's own tests with the installed venv, and a `say`-generated Spanish sentence transcribed with `--model tiny --no-diarize`.
    - **release**: on tags, attaches the `.dmg` to the GitHub release.

## Project Structure

```text
app/core/platform_paths.py          # config/local data dirs per OS; venv python path
app/core/config.py                  # uses platform_paths; engine dir first on macOS
app/core/output_path.py             # local base via platform_paths
app/transcription/integration.py    # transcripts_base + venv python via platform_paths
app/transcription/worker.py         # posix: new session, nice, caffeinate, fcntl lock
app/transcription/engine_setup.py   # first-use engine install (state machine)
app/transcription/hf_token.py       # check / store / mask the token
app/capture/sources.py              # per-OS facade: sources, preview frame, captures
app/capture/frame_pipe.py           # constant-rate BGRA -> ffmpeg writer (macOS)
app/capture/audio_gaps.py           # timestamp -> silence padding (pure, tested)
app/capture/mac_sck.py              # ScreenCaptureKit: content, streams, video/audio captures
app/core/mac_permissions.py         # screen + mic permission check/request/open settings
app/ui/hotkeys_mac.py               # Carbon global hotkeys
app/ui/mac_window.py                # sharingType none for our window
app/ui/engine_dialogs.py            # consent + progress, token dialog (macOS)
app/main.py, app/ui/main_window.py  # wire the above behind sys.platform checks
transcriptor/requirements.lock.macos.txt     # macOS 14+ (validated versions)
transcriptor/requirements.lock.macos13.txt   # macOS 13 (unverified)
packaging/macos/{launcher.py, MeetingRecorder.spec, build_dmg.sh, LEEME - Primera vez.txt}
tools/mac_engine_check.py, tools/mac_capture_check.py
.github/workflows/macos.yml
tests/test_platform_paths.py, test_engine_setup.py, test_hf_token.py, test_audio_gaps.py
README.md, CLAUDE.md
```

## Verification map

| Requirement | Where it is proven |
|---|---|
| FR-001/002/004, SC-007 | CI build job: `.dmg` exists, under 500 MB, app launches headless (`--self-check`) |
| FR-005/006/008/010 | CI capture probe (best effort) + user's Mac |
| FR-007, FR-009, FR-011 | User's Mac |
| FR-013/014/015/016, SC-003/004 | Windows unit tests (state machine, interruption, token) + CI engine job (real install + transcript) + user's Mac |
| FR-017/018 | Existing suite on macOS CI + unit tests for paths |
| FR-019/020, SC-005 | Workflow runs on push and tag |
| FR-021, SC-006 | Windows suites + `verify_transcription.py --quick` + `verify_pipeline.py` on this machine |

## Complexity Tracking

> No constitution violations; section intentionally empty.
