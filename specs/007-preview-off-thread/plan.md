# Plan: Lightweight Off-Thread Preview

**Feature**: `007-preview-off-thread` | **Date**: 2026-07-28

## Summary

Move idle WGC one-shot grabs off the Qt GUI thread; deliver `QImage` via signal; coalesce in-flight work; use FastTransformation for scale. Add `grab_monitor_frame` for screen sources so preview does not need `grabWindow` on the GUI thread.

## Constitution

Recording Always Wins: preview never restarts capture devices mid-recording; recording path prefers `current_video_frame()`.

## Approach

1. `grab_monitor_frame(monitor_index)` mirror of `grab_window_frame`.
2. MainWindow: `_preview_ready_sig(QImage, int gen)`, `_preview_busy`, `_preview_dirty`, `_preview_gen`.
3. `_update_preview`: if recording+frame → apply sync (cheap). Else schedule daemon thread if not busy; else mark dirty.
4. Worker: grab → numpy → `QImage.copy()` → emit.
5. Slot: ignore stale gen; `QPixmap.fromImage` + FastTransformation scale.
6. Light unit/smoke: MainWindow still constructs; optional test that schedule path sets busy flag.

## Files

- `app/capture/windows_video.py`
- `app/ui/main_window.py`
- `tests/test_preview_async.py` (optional light)
- `specs/007-preview-off-thread/*`
