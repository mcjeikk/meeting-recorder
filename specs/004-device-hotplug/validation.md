# Validation Report: Device Hotplug Auto-Refresh

**Feature**: `004-device-hotplug`  
**Date**: 2026-07-28  
**Scope**: Evidence grounding before plan/tasks (claims vs code + light OS docs)

## What was validated

| Area | Method |
|------|--------|
| Manual mic refresh (001) | Code: `_refresh_mics(manual=True)` + `list_microphones(refresh=…)` + PortAudio `_terminate/_initialize` only when idle |
| Recording Always Wins | Code + constitution: mid-recording refresh skips PortAudio reinit; status message points user to stop + Actualizar |
| Native Win32 filter pattern | Existing `GlobalHotkeys(QAbstractNativeEventFilter)` + `installNativeEventFilter` — reusable pattern for device messages |
| PortAudio hotplug limits | sounddevice issues #125/#343; PortAudio HotPlug wiki: device list frozen at `Pa_Initialize`; stable Windows build lacks exposed `Pa_RefreshDeviceList` in sounddevice |
| OS audio notifications | Microsoft Learn: `IMMNotificationClient` (MMDevice) for endpoint add/remove/state; also `WM_DEVICECHANGE` for PnP (noisier, often `DBT_DEVNODES_CHANGED`) |
| Scope vs multi-monitor | Sources use `list_windows` / WGC monitor — not audio hotplug; FR-008 keeps video auto-refresh out |
| Dependencies | No comtypes/pycaw today; ctypes + Qt filter already in tree |

## Assumptions locked for plan

1. **Detect** device-change with a lightweight Windows notification path (prefer MMDevice callback if low-complexity; else debounced `WM_DEVICECHANGE`), then call existing idle refresh path.
2. **Idle deep refresh** = stop AudioMonitor → `list_microphones(refresh=True)` → restore selection → reattach monitor (same as manual).
3. **During recording** = never deep-reinit; mark pending refresh and run deep refresh once idle after stop (or ignore until next idle event).
4. **Debounce** ≈ 500–1500 ms; optional short delayed second pass for BT HFP (≤ ~2–3 s) without polling loops.
5. Manual **Actualizar** button remains; video source auto-refresh out of MVP.
6. No new heavy deps if ctypes/Qt suffice; add comtypes only if MMDevice COM proves too painful.

## Residual risks

- BT Hands-Free may appear seconds after first PnP event — debounce + delayed second refresh mitigates; manual Actualizar remains fallback.
- Non-audio `WM_DEVICECHANGE` noise if using that API alone — filter/debounce required.
- Mid-recording soft list without reinit still won’t show brand-new PortAudio devices — acceptable per SC-002 / FR-003.

## Recommendation

**GO** — proceed to plan + tasks + Phase 1 implement (small reuse of 001 path).
