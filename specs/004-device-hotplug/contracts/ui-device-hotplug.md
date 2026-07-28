# Contract: UI Device Hotplug

**Feature**: `004-device-hotplug`  
**Date**: 2026-07-28

## DeviceChangeWatcher

- Installed as `QAbstractNativeEventFilter` alongside hotkeys (does not steal events; returns `(False, 0)`).
- On relevant `WM_DEVICECHANGE`, invokes a single callback (no device enumeration inside the filter).
- Windows-only; no-op construction on other platforms.

## MainWindow orchestration

| Trigger | Behavior |
|---------|----------|
| Watcher callback | Restart debounce timer (~800 ms) |
| Debounce fire, idle | `_refresh_mics(auto=True)` → deep PortAudio reinit path |
| Debounce fire, recording | Set `pending_deep_refresh`; do **not** call `list_microphones(refresh=True)` |
| Recording → idle, pending | Clear pending; `_refresh_mics(auto=True)` |
| Manual Actualizar | Unchanged (`manual=True`) |
| Optional follow-up | After successful idle auto refresh, one delayed second auto refresh (~2 s); skip/cancel if recording |

## Status copy (auto)

- Same families as 001: count found, selection lost, “sin cambios”, BT Hands-Free hint when applicable.
- Must not claim the user pressed Actualizar.

## Non-goals

- Auto-refresh of video source combo.
- Settings toggle.
- Killing/reinit PortAudio while `is_recording()`.
