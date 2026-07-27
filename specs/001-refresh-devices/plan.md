# Implementation Plan: Refresh Capture Devices

**Branch**: `001-refresh-devices` | **Date**: 2026-07-27 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-refresh-devices/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

El usuario debe poder **refrescar manualmente** la lista de micrófonos (hoy solo se llena al arranque) con la misma claridad que el refresco de ventanas/pantalla, **conservando la selección** cuando el dispositivo sigue disponible y **sin interrumpir** una grabación en curso. El cambio de mic en caliente (`Recorder.change_mic` / `MicCapture.switch_device`) ya existe y se reutiliza; el trabajo es UI + lógica de repoblación/selección + reenganche del `AudioMonitor` fuera de grabación. Hotplug automático queda fuera de MVP.

## Technical Context

**Language/Version**: Python 3.11.9 (venv del Recorder: `.venv`)

**Primary Dependencies**: PySide6 (UI), sounddevice (enumeración WASAPI de mics), captura existente en `app/capture/*`

**Storage**: N/A (solo estado en memoria de combos + `AppConfig.last_mic_name` ya existente para arranque)

**Testing**: smoke/headless UI (`QT_QPA_PLATFORM=offscreen`, construir `MainWindow` sin `show()`); verificación manual de dispositivos reales; tests unitarios ligeros de lógica de selección si se extrae helper

**Target Platform**: Windows desktop (PySide6)

**Project Type**: desktop-app (single project)

**Performance Goals**: lista de mics/fuentes visible en &lt; 3 s tras pulsar Actualizar (SC-001); UI no congelada varios segundos (FR-008)

**Constraints**: refresco **manual** solamente; durante grabación, fuente de video bloqueada y mic disponible; identidad de mic = nombre visible exacto; Recording Always Wins (enumeración no debe matar ni pausar la grabación)

**Scale/Scope**: un usuario local; ~2 selectores en `MainWindow`; sin backend, sin hotplug, sin cambio de fuente mid-recording

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Recording Always Wins | PASS | Refresh de mics es bajo demanda; no inicia jobs de fondo; no detiene grabación; `change_mic` reutilizado. Enumeración síncrona breve en UI thread o feedback inmediato si se mueve a worker — no suspender captura. |
| II. Privacy Is Local by Default | PASS | Solo enumera dispositivos locales; sin red ni cloud. |
| III. Transcription Stays a Sibling Subprocess | N/A | Sin cambios en cola/CLI Transcriptor. |
| IV. Paths and Processes Must Be Robust | PASS | Sin nuevos subprocesos ni rutas; `list_microphones` / `list_windows` in-process. |
| V. Simplicity for a Single Power User | PASS | Extiende patrón UI existente (botón Actualizar + conservar selección); sin servicios, hotplug ni abstracciones nuevas. |

**Gate result (pre-design)**: PASS — sin violaciones que justificar.

**Gate result (post-Phase 1)**: PASS — diseño no introduce workers programados, hotplug, ni fusión de venvs; contratos UI locales solamente.

## Project Structure

### Documentation (this feature)

```text
specs/001-refresh-devices/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── ui-refresh-devices.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
app/
├── ui/
│   └── main_window.py          # Botón refresh mics, _on_refresh / _refresh_mics / _refresh_sources, UI recording gates
├── capture/
│   ├── windows_audio.py        # list_microphones() (reutilizar; sin cambio de contrato salvo bugs)
│   ├── windows_video.py        # list_windows() (reutilizar)
│   └── monitor.py              # AudioMonitor.set_mic / start — reenganche post-refresh
├── core/
│   ├── config.py               # AudioDevice, VideoSource, AppConfig.last_mic_name
│   └── orchestrator.py         # Recorder.change_mic (reutilizar mid-recording)
smoke_test.py                   # smoke existente; ampliar solo si aporta cobertura headless
```

**Structure Decision**: Single desktop app under `app/`. Toda la feature vive en la capa UI (`main_window.py`) reutilizando APIs de captura ya existentes; no hay módulo nuevo ni capa de servicios.

## Complexity Tracking

> Sin violaciones de constitución — tabla vacía a propósito.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Implementation Approach (guidance for `/speckit-tasks`)

1. **UI mic refresh**: añadir control explícito “Actualizar” en la sección Micrófono (paridad con fuentes). El botón de fuentes sigue refresca**ndo solo** ventanas/pantalla.
2. **`_refresh_mics`**: guardar nombre (o “Sin micrófono”) previo; repoblar vía `list_microphones()`; restaurar por `findText` / match de nombre exacto; si desapareció → fallback seguro + mensaje breve en `_status_label` (FR-007).
3. **Post-refresh monitor**: si **no** se graba, llamar `AudioMonitor.set_mic` (o reinicio equivalente) con la selección actual (FR-005).
4. **Durante grabación**: mic combo + botón refresh de mics habilitados; fuente combo + refresh de fuentes deshabilitados (FR-006); al elegir otro mic tras refresh, `_on_mic_activated` → `change_mic` (ya cableado).
5. **Fuentes**: mantener `_refresh_sources` (ya conserva ventana / pantalla completa); `_on_refresh` no debe llamar a mics.
6. **No hotplug**, no cambio de video mid-recording, no tocar Transcriptor.
