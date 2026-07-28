# Research: Device Hotplug Auto-Refresh

**Feature**: `004-device-hotplug`  
**Date**: 2026-07-28

## R1 — How to detect device changes on Windows?

**Decision**: Debounced `WM_DEVICECHANGE` via `QAbstractNativeEventFilter` (same pattern as `GlobalHotkeys`), reacting to `DBT_DEVICEARRIVAL`, `DBT_DEVICEREMOVECOMPLETE`, and `DBT_DEVNODES_CHANGED`. Optional `RegisterDeviceNotification` for audio capture/render interface GUIDs if top-level broadcasts prove too sparse in manual tests.

**Rationale**: No new deps; ctypes already used; MMDevice `IMMNotificationClient` is more precise but heavier (COM class in ctypes or new comtypes dep). Validation recommended WM_DEVICECHANGE for MVP.

**Alternatives considered**:
- IMMNotificationClient / pycaw — better audio filtering; deferred if WM path too noisy or misses BT.
- Periodic polling of `list_microphones()` — wastes CPU; still needs PortAudio reinit to see new devices.
- PortAudio `Pa_SetDevicesChangedCallback` — not exposed by sounddevice’s bundled PortAudio on Windows.

## R2 — What happens on notification?

**Decision**: Restart a single-shot `QTimer` (~800 ms). On timeout: if idle → `_refresh_mics(auto=True)` (deep reinit + selection preserve + monitor reattach). If recording → set `_pending_mic_hotplug_refresh = True` only. On recording stop (enter idle): if pending → clear flag and run auto refresh once. Optional second single-shot (~2 s later) only after an auto deep refresh when idle, to catch late BT HFP — cancel if recording starts.

**Rationale**: Matches FR-003/FR-005 and SC-001/SC-002; reuses 001 path.

## R3 — API shape for `_refresh_mics`

**Decision**: Add `auto: bool = False`. Deep reinit when `(manual or auto) and not recording`. Status strings: auto uses similar copy to manual (“N micrófonos…”) without implying the user pressed the button; mid-recording auto does not call into deep path.

**Alternatives**: Always call `manual=True` from auto — works but muddies telemetry/status semantics.

## R4 — Filter non-audio noise

**Decision**: Debounce absorbs bursts. Do not special-case every device type in MVP. If manual testing shows excessive refreshes from USB storage, tighten to audio interface GUIDs via `RegisterDeviceNotification` (same module).

## R5 — Video sources

**Decision**: Out of scope (FR-008). Window list changes are not audio PnP; keep source Actualizar button.

## Open questions

Ninguna bloqueante. Si BT HFP tarda >5 s de forma habitual, documentar segundo delay o pedir Actualizar — no bloquea ship.
