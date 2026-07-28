# Data Model: Device Hotplug Auto-Refresh

**Feature**: `004-device-hotplug`  
**Date**: 2026-07-28

Sin persistencia nueva. Estado en memoria de la sesión UI:

## DeviceChangeEvent (lógico)

| Field | Type | Notes |
|-------|------|-------|
| kind | arrival / removal / nodes_changed | Mapeo desde `wParam` de `WM_DEVICECHANGE` |
| received_at | timestamp | Implícito al armar el debounce |

## UiHotplugState (MainWindow)

| Field | Type | Notes |
|-------|------|-------|
| debounce_timer | single-shot ~800 ms | Reinicia en cada evento |
| pending_deep_refresh | bool | True si hubo evento durante grabación |
| followup_timer | single-shot ~2 s | Opcional post-refresh idle (BT HFP) |

## MicSelection (existente)

Identidad = nombre exacto en combo (sin cambio respecto a 001).
