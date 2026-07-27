# Research: Refresh Capture Devices

**Feature**: `001-refresh-devices`  
**Date**: 2026-07-27  
**Status**: Complete — no open NEEDS CLARIFICATION

## R1 — Where should mic refresh live in the UI?

**Decision**: Botón **Actualizar** dedicado en la sección Micrófono (junto al combo), independiente del botón de fuentes.

**Rationale**: FR-001 exige acción explícita en la sección de Micrófono. Hoy `_on_refresh` solo llama `_refresh_sources()`; mezclar ambos en un solo botón ocultaría el hueco de mics y contradice la paridad visual con “¿Qué quieres grabar?”.

**Alternatives considered**:
- Un solo botón global que refresque fuentes + mics — rechazado: el spec pide acción en la sección Micrófono; además durante grabación el botón de fuentes se deshabilita y los mics deben seguir refresables.
- Menú contextual / atajo de teclado solamente — rechazado: menos descubrible; MVP es botón visible.

## R2 — How to preserve mic selection across refresh?

**Decision**: Conservar por **nombre exacto** del ítem del combo (`AudioDevice.name` / texto “Sin micrófono”), igual que fuentes usan título de ventana. Si no hay match → fallback a “Sin micrófono” (o primer mic disponible si se prefiere consistencia con arranque) **y** mensaje breve en la barra de estado.

**Rationale**: Spec Assumptions: “Los nombres de dispositivo que muestra el SO son la clave de identidad”. `_refresh_sources` ya usa `findText` / `currentData`; `_refresh_mics` hoy fuerza `setCurrentIndex(1)` — eso viola FR-003/SC-002.

**Alternatives considered**:
- Match por `AudioDevice.index` — rechazado: índices WASAPI cambian al enchufar/desenchufar.
- Fuzzy match / substring Bluetooth — diferido; edge case del spec dice preferir exacto y no forzar índice arbitrario sin avisar.
- Persistir GUID WASAPI — over-engineering (Principio V); nombres bastan para un usuario.

## R3 — AudioMonitor after mic list refresh (idle)

**Decision**: Tras repoblar y fijar selección, si **no** hay grabación activa, invocar `AudioMonitor.set_mic(selected)` (API existente). No hace falta rediseñar el monitor.

**Rationale**: FR-005; `_on_mic_activated` ya llama `set_mic` en idle, pero un refresh que restaura el mismo índice con `blockSignals(True)` **no** dispara `activated` — hay que reenganchar explícitamente.

**Alternatives considered**:
- `stop()` + `start(device)` completo — innecesario si `set_mic` ya cierra/abre el stream de mic.
- No tocar el monitor hasta que el usuario re-seleccione — rechazado: viola FR-005 y SC medidor.

## R4 — Behavior while recording

**Decision**: Mantener gates actuales: `source_combo` + refresh de fuentes **deshabilitados**; combo de mic + **nuevo** refresh de mics **habilitados**. Tras refresh, cambio de mic vía `_on_mic_activated` → `Recorder.change_mic` → `MicCapture.switch_device`.

**Rationale**: FR-006 + Assumptions; hot-swap ya probado en producción. Principio I: no detener grabación por enumeración.

**Alternatives considered**:
- Deshabilitar también refresh de mics mid-recording — rechazado: el usuario necesita listar un mic recién conectado para cambiar en caliente.
- Permitir cambio de fuente mid-recording — fuera de alcance explícito.

## R5 — Threading / UI freezes during enumeration

**Decision**: Mantener enumeración **síncrona** en el hilo UI para MVP (`list_microphones` / `list_windows` son llamadas locales rápidas). Feedback: la lista cambia y/o un texto breve en `_status_label` (“Micrófonos actualizados” / “Micrófono ya no disponible…”). Solo si en pruebas reales el enumerado bloquea &gt; ~1 s, se considera `QThread`/`QTimer` — no planificarlo de antemano.

**Rationale**: Principio V (simplicidad); SC-001 (&lt; 3 s) es alcanzable in-process. Evitar workers por defecto.

**Alternatives considered**:
- Worker thread desde el día 1 — rechazado como prematuro.
- Hotplug IMMDevice notifications — fuera de MVP (Assumptions).

## R6 — Startup vs manual refresh selection policy

**Decision**: En **arranque**, conservar el flujo actual: `_refresh_mics()` + `_apply_saved_config()` que restaura `last_mic_name`. En **refresh manual**, conservar la selección **actual de la UI** (no re-aplicar ciegamente config ni forzar índice 1).

**Rationale**: Separar “preferencia de sesión previa” de “no saltar la elección del usuario al refrescar”.

**Alternatives considered**:
- Siempre aplicar `last_mic_name` en cada refresh — puede sobrescribir una elección reciente no guardada aún; peor UX.

## R7 — Source refresh parity

**Decision**: No reescribir `_refresh_sources`; solo asegurar que `_on_refresh` sigue limitado a fuentes + preview, y que el botón permanece deshabilitado durante grabación. Historia P3 es regresión/paridad, no feature nueva.

**Rationale**: El código ya conserva ventana seleccionada y pantalla completa (`userData=None` permanece índice 0 si `prev` no es `VideoSource`).

## Open questions

Ninguna. Clarificaciones del spec (manual-only, nombre como identidad, hot-swap reutilizado) son suficientes para diseño e implementación.
