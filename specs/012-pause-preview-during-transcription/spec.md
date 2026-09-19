# Feature Specification: Pause Idle Preview While Transcribing

**Feature Branch**: `012-pause-preview-during-transcription`

**Created**: 2026-09-08

**Status**: Draft

**Input**: User description: "Llega un punto donde el programa se cierra de la nada mientras está transcribiendo, me ha pasado como 4 veces hoy"

## Clarifications

### Session 2026-09-08

Windows Application Error / WER on this machine (2026-09-08, four times): `pythonw.exe` (the Recorder) APPCRASH / BEX64 in `igd10um64xe.DLL` (Intel Graphics user-mode driver), exception `c0000005` / `c0000409`. A separate sibling-process crash (`python.exe` + `hf_xet.pyd`) can fail a job but does not close the Recorder window.

- Q: Is this a graceful quit? → A: No. It is a native crash. `closeEvent` is not involved.
- Q: What in the Recorder hits that DLL while transcribing? → A: Idle **Windows Graphics Capture** preview: every ~1.5 s the app opens a short WGC/D3D session (`grab_window_frame` / `grab_monitor_frame`) even when not recording. Under transcription CPU/GPU pressure the Intel driver faults and kills the UI. Recording preview that reuses the already-open capture session is a different path.
- Q: Must preview stay live during transcription? → A: No. The user is waiting on a transcript, not composing a new recording. Freeze the last thumbnail; resume idle WGC when no transcription is queued or running.

### Session 2026-09-11

Windows Application Error 1000 at 00:21:46: `pythonw.exe` APPCRASH in `igd10um64xe.DLL` (`c0000005`), modules include `GraphicsCapture.dll` / `d3d11.dll`. The job *Reunion Simple 10 de sept 2026.m4a* had already finished at 23:18:47; the UI stayed open and the ~1.5 s idle WGC loop resumed, then the Intel driver killed the process. Pausing only while a job is open is not enough.

- Q: Resume periodic idle WGC after the job completes? → A: No. Periodic `grab_window_frame` / `grab_monitor_frame` (new WGC session every ~1.5 s) is forbidden. One-shot grabs on source change / Actualizar remain allowed when no job is open. Recording preview still uses the live backend frame.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Recorder stays open during a long transcription (Priority: P1)

As the primary user, I start a transcription (meeting or imported file) and leave the Recorder window open. The window must remain until I close it. The last preview frame may freeze.

**Why this priority**: Four hard crashes today; the transcript child already survives an app close, but losing the UI mid-job is alarming and looks like data loss.

**Independent Test**: With a transcription queued or running and not recording, confirm idle WGC preview grabs are not scheduled. After the job finishes, idle preview may resume.

**Acceptance Scenarios**:

1. **Given** a transcription is pending, extracting, or running and the user is not recording, **When** the UI would have refreshed the idle preview, **Then** it must not start a new WGC grab.
2. **Given** that transcription finishes or is cancelled, **When** the next idle refresh would be due, **Then** the periodic WGC loop still must not start; a one-shot grab is allowed only if the user changes source or clicks Actualizar.
3. **Given** the user is recording, **When** a transcription is also paused/queued, **Then** live preview from the active recording session still updates (no new idle WGC session).

### Edge Cases

- Several queued jobs: preview stays paused for the whole open-job stretch.
- Window minimized: existing monitor-stop behavior unchanged.
- Out of scope: fixing the Intel driver; rewriting WGC; HuggingFace `hf_xet` crashes inside Transcriptor (job may fail; Recorder must still stay up).

## Requirements *(mandatory)*

- **FR-001**: While a transcription job is pending, extracting, or running, and the user is not recording, the Recorder MUST NOT open a new idle WGC/D3D preview capture.
- **FR-002**: When no such job is open, a one-shot idle preview grab (source change or Actualizar) MAY run. The periodic ~1.5 s idle WGC loop MUST NOT run.
- **FR-003**: Recording-time preview that uses the in-progress capture frame MUST still be allowed.
- **FR-004**: The last preview image MAY remain on screen while paused; the app MUST NOT crash or quit because preview was skipped.

## Success Criteria *(mandatory)*

- **SC-001**: 100% of idle preview scheduling decisions skip WGC when a transcription is open and the user is not recording (unit-testable).
- **SC-002**: After this change, a typical multi-hour Equilibrado/Máxima job on this Intel GPU machine must not reproduce the `igd10um64xe.DLL` APPCRASH as a result of idle preview (manual; WER should no longer pair those crashes with an open Recorder preview loop).

## Assumptions

- The four WER events today are the same defect the user felt.
- Pausing idle preview is enough; we do not need to stop PortAudio meters for this crash signature.
