# Implementation Plan: Device Hotplug Auto-Refresh

**Branch**: `004-device-hotplug` | **Date**: 2026-07-28 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-device-hotplug/spec.md`

## Summary

Disparar automáticamente el refresh profundo de micrófonos (ya implementado en 001) cuando Windows notifica cambios de dispositivos, con debounce y **sin reiniciar PortAudio durante grabación**. Diferir refresh profundo a idle si el evento llega mid-recording. El botón Actualizar manual permanece.

## Technical Context

**Language/Version**: Python 3.11.9 (Recorder `.venv`)

**Primary Dependencies**: PySide6 (`QAbstractNativeEventFilter`, `QTimer`); ctypes Win32 (`WM_DEVICECHANGE`); `sounddevice` via `list_microphones(refresh=True)` existente

**Storage**: N/A (sin config nueva en MVP)

**Testing**: unit tests del watcher (mensaje → callback) + debounce/pending flag; headless MainWindow smoke opcional; quickstart manual BT/USB

**Target Platform**: Windows desktop

**Project Type**: desktop-app

**Performance Goals**: lista actualizada ≤ ~5 s en idle tras evento SO (SC-001); 0 cortes de grabación (SC-002)

**Constraints**: Constitution I (nunca deep-reinit mid-recording); V (sin MMDevice COM / deps nuevas si WM_DEVICECHANGE basta); reutilizar `_refresh_mics`

**Scale/Scope**: un usuario; solo mics (no auto-refresh de ventanas/monitores)

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Recording Always Wins | PASS | Deep PortAudio reinit solo idle; pending flag mid-recording |
| II. Privacy Is Local by Default | PASS | Solo notificaciones locales del SO |
| III. Transcription Stays a Sibling Subprocess | PASS | No toca Transcriptor |
| IV. Paths and Processes Must Be Robust | PASS | Sin nuevos subprocess |
| V. Simplicity for a Single Power User | PASS | Un watcher + debounce; reusa 001; sin UI settings |

**Gate result (pre-design)**: PASS  
**Gate result (post-Phase 1)**: PASS

## Project Structure

### Documentation (this feature)

```text
specs/004-device-hotplug/
├── plan.md
├── research.md
├── data-model.md
├── validation.md
├── quickstart.md
├── contracts/
│   └── ui-device-hotplug.md
└── tasks.md
```

### Source Code (repository root)

```text
app/
├── ui/
│   ├── device_watcher.py   # NEW: WM_DEVICECHANGE → callback
│   └── main_window.py      # debounce timer, pending refresh, wire watcher
tests/
└── test_device_hotplug.py  # watcher + pending/idle policy (mocked)
```

**Structure Decision**: Nuevo módulo pequeño de watcher (paridad con `hotkeys.py`); UI orquesta debounce y llama `_refresh_mics`.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
