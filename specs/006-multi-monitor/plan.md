# Implementation Plan: Multi-Monitor Source Selection

**Branch**: `006-multi-monitor` | **Date**: 2026-07-28 | **Spec**: [spec.md](./spec.md)

## Summary

Enumerate Windows monitors, expose each as a screen `VideoSource` with 1-based `monitor_index`, pass that index into WGC capture, and make idle preview follow the selected monitor. Window capture unchanged.

## Technical Context

**Language/Version**: Python 3.11.9 / PySide6 / windows-capture  
**Testing**: unit test for `list_monitors` shape; headless UI smoke if feasible  
**Constraints**: Recording Always Wins; no mid-recording source switch (existing disable)

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. RAW | PASS | Source combo still disabled while recording |
| III. Sibling | PASS | Capture-only; no Transcriptor |
| V. Simplicity | PASS | Reuse VideoSource + combo |

## Project Structure

```text
app/core/config.py              # VideoSource.monitor_index + label
app/capture/windows_video.py    # list_monitors(); WGC uses source.monitor_index
app/ui/main_window.py           # _refresh_sources / preview / _build_settings
tests/test_multi_monitor.py     # list_monitors + label
```

## Approach

1. `list_monitors()` via ctypes `EnumDisplayMonitors` → `VideoSource(kind="screen", title=…, monitor_index=i)`.
2. Labels: `Pantalla N (principal)` / `Pantalla N` + optional size.
3. WGC: `monitor_index=self._source.monitor_index or 1`.
4. UI: add each monitor as combo item (no more `userData=None` screen).
5. Preview: map index to `QGuiApplication.screens()` (best-effort by order/geometry) or grab via index; refine async in 007.
6. Preserve selection on refresh by `monitor_index` then title.

## gdigrab fallback

If WGC fails, `WindowsVideoCapture` gdigrab `desktop` may only capture primary — acceptable degradation; status/error path unchanged.
