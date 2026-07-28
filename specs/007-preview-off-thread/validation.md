# Validation: Lightweight Preview

**Date**: 2026-07-28

| Claim | Evidence |
|-------|----------|
| GUI classes not reentrant | Qt 6 Threading Basics — widgets/QPixmap main thread only |
| Offload pattern | Worker + queued signal; QImage from bytes OK off-thread |
| Current cost | `_update_preview` calls `grab_window_frame` and `QScreen.grabWindow` on timer path |
| WGC free-threaded | Existing `grab_window_frame` already uses `start_free_threaded` |

**GO** — worker thread + coalesce + FastTransformation.
