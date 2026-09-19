# Implementation Plan: Pause Idle Preview While Transcribing

**Branch**: `012-pause-preview-during-transcription` | **Date**: 2026-09-08 | **Spec**: [spec.md](./spec.md)

## Summary

WER shows Recorder (`pythonw.exe`) crashing in the Intel GPU driver during idle WGC preview while transcription runs. Gate idle `grab_window_frame` / `grab_monitor_frame` when a job is open; keep recording preview on the live backend frame.

## Technical Context

**Language/Version**: Python 3.11.9 / PySide6  
**Testing**: unittest on `preview_policy` (no devices)  
**Constraints**: Constitution I (recording preview stays); do not fuse Transcriptor

## Constitution Check

PASS — does not change subprocess transcription; only skips idle GPU grabs.

## Source

- `app/ui/preview_policy.py` (new)
- `app/ui/main_window.py` (`_update_preview`, `_tick`)
- `tests/test_preview_policy.py`
