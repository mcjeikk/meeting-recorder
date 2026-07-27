# UI Contract: Refresh Capture Devices

**Feature**: `001-refresh-devices`  
**Date**: 2026-07-27  
**Surface**: Desktop UI (`MainWindow`) — no HTTP/CLI API

## Purpose

Contrato observable entre usuario y app para refrescar listas de captura. Los implementadores deben satisfacer estos comportamientos; los detalles de widgets pueden variar si el contrato se cumple.

---

## C-MIC-REFRESH — Actualizar micrófonos

| Aspect | Contract |
|--------|----------|
| **Trigger** | Acción explícita en la sección “Micrófono” (botón etiquetado de forma inequívoca, p. ej. “Actualizar”). |
| **Precondition** | App visible; disponible en idle **y** durante grabación. |
| **Effect** | Repoblar el selector de micrófonos con el enumerado actual del sistema (WASAPI / `list_microphones`). Incluir siempre la opción “Sin micrófono”. |
| **Selection** | Si el nombre previamente seleccionado sigue en la lista → permanece seleccionado. Si no → fallback seguro + mensaje breve de estado. |
| **Side effects (idle)** | El medidor de nivel usa el micrófono seleccionado tras el refresh (`AudioMonitor`). |
| **Side effects (recording)** | La grabación **no** se detiene. El dispositivo de captura de mic no cambia hasta que el usuario elija otro ítem (entonces aplica hot-swap existente). |
| **Feedback** | La lista refleja el resultado (y/o mensaje de estado). Completar en &lt; 3 s en condiciones normales. |
| **Non-goals** | Auto-refresh por hotplug; diálogos bloqueantes obligatorios. |

### Acceptance mapping

- FR-001, FR-003, FR-005, FR-006, FR-007, FR-008  
- SC-001, SC-002, SC-003, SC-004  

---

## C-SRC-REFRESH — Actualizar fuentes de video

| Aspect | Contract |
|--------|----------|
| **Trigger** | Botón “Actualizar” existente en “¿Qué quieres grabar?”. |
| **Precondition** | Solo cuando **no** se está grabando (control deshabilitado durante grabación). |
| **Effect** | Repoblar pantallas/ventanas (`list_windows` + ítem pantalla completa). |
| **Selection** | Conservar ventana por título si sigue abierta; si era pantalla completa, permanecer en pantalla completa. |
| **Side effects** | Actualizar vista previa según la selección resultante. |
| **Non-goals** | Cambiar fuente mid-recording; refrescar mics desde este botón. |

### Acceptance mapping

- FR-002, FR-004, FR-006  
- SC-004, SC-005  

---

## C-MIC-SELECT — Cambio de micrófono (post-refresh o manual)

| Aspect | Contract |
|--------|----------|
| **Trigger** | Usuario elige un ítem del combo de micrófono. |
| **Idle** | `AudioMonitor` apunta al dispositivo elegido (o se detiene el stream de mic si “Sin micrófono”). |
| **Recording** | Hot-swap vía orquestador; grabación continúa; audio del nuevo mic entra en la pista (segmentos existentes). |
| **Invariant** | No altera la fuente de video. |

### Acceptance mapping

- User Story 1 escenario 3; User Story 2 escenario 2  
- FR-005, FR-006  

---

## C-RECORDING-GATES — Controles durante grabación

| Control | Idle | Recording |
|---------|------|-----------|
| Source combo | enabled | **disabled** |
| Source refresh | enabled | **disabled** |
| Mic combo | enabled | **enabled** |
| Mic refresh | enabled | **enabled** |

Violating this table is a contract failure (FR-006).

---

## Error / empty states

| Condition | Required UI behavior |
|-----------|----------------------|
| Ningún micrófono hardware | Solo “Sin micrófono”; sin excepción no manejada |
| Mic seleccionado desaparece tras refresh | Fallback + mensaje breve en estado |
| Enumeración falla / excepción | App usable; lista vacía o previa; mensaje de estado preferible a crash |

---

## Explicit non-contracts (out of MVP)

- Notificaciones del SO al enchufar dispositivos  
- APIs públicas para otros procesos  
- Cambio de ventana/pantalla durante grabación  
