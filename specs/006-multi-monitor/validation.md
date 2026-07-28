# Validation Report: Multi-Monitor Source Selection

**Feature**: `006-multi-monitor`  
**Date**: 2026-07-28

## What was validated

| Area | Method |
|------|--------|
| Current hardcode | Code: `WindowsGraphicsCapture` uses `monitor_index=1` for screen |
| UI | `_refresh_sources` adds single `Pantalla completa` with `userData=None` |
| Library API | `windows_capture.WindowsCapture(..., monitor_index: Optional[int])` — 1-based |
| Rust enum | windows-capture `Monitor::from_index` / `enumerate` via `EnumDisplayMonitors` |
| Win32 | Local probe: `EnumDisplayMonitors` + `GetMonitorInfoW` yields `\\.\DISPLAYN`, PRIMARY flag, rect |
| Preview | Idle screen path uses `QApplication.primaryScreen().grabWindow(0)` — primary only today |
| Microsoft WGC | `IGraphicsCaptureItemInterop::CreateForMonitor(HMONITOR)` supports per-monitor items |

## Assumptions locked

1. Enumerate monitors with Win32 `EnumDisplayMonitors` (same order as windows-capture); index = 1-based position.
2. Extend `VideoSource` with `monitor_index` for `kind=="screen"`.
3. Replace single null screen entry with one `VideoSource` per monitor.
4. Preview: grab selected screen (Qt `QGuiApplication.screens()` matched by geometry/index, or WGC one-shot) — full off-thread work may land in 007.
5. gdigrab fallback remains best-effort (primary desktop); document in plan.

## Recommendation

**GO** — implement.
