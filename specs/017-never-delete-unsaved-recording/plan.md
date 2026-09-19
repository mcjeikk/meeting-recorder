# Implementation Plan: Never Delete an Unsaved Recording

**Branch**: `017-never-delete-unsaved-recording`  
**Date**: 2026-09-09  
**Spec**: [spec.md](./spec.md)

## Technical choices

- Session folders live under `%LOCALAPPDATA%\MeetingRecorder\sessions\` (not `%TEMP%`).
- FFmpeg always muxes to `%LOCALAPPDATA%\MeetingRecorder\saves\<stem>.mp4` (short path).
- Copy to the user folder uses `\\?\` on Windows; size is verified before any delete.
- `pending_save.json` survives restart. `Recorder.retry_save` copies or remuxes.
- `_finalize` no longer `rmtree`s in `finally`. Cleanup only after verified destination.

## Tests

- `tests/test_save_safety.py`: empty folder, long path, mux fail keeps session, copy fail + retry, success cleans up.
