# Feature Specification: Multi-Monitor Source Selection

**Feature Branch**: `006-multi-monitor`

**Created**: 2026-07-28

**Status**: Draft

**Input**: User description: "Multi-monitor source selection — choose which monitor for pantalla completa screen capture (not only the primary)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Choose which screen to record (Priority: P1)

El usuario tiene más de un monitor. En el selector de fuente ve una entrada por pantalla (p. ej. «Pantalla 1 (principal)», «Pantalla 2») además de las ventanas. Al elegir una pantalla secundaria y grabar, el video corresponde a ese monitor.

**Why this priority**: Hoy «Pantalla completa» fija el monitor principal; reuniones en el segundo monitor quedan fuera.

**Independent Test**: Con ≥2 monitores, seleccionar Pantalla 2, grabar unos segundos, verificar que el contenido es del segundo monitor.

**Acceptance Scenarios**:

1. **Given** N monitores detectados, **When** se abre el combo de fuentes, **Then** hay N entradas de pantalla con etiquetas distinguibles (principal marcada).
2. **Given** Pantalla k seleccionada, **When** inicia la grabación (ruta WGC), **Then** la captura usa ese monitor.
3. **Given** un solo monitor, **When** se listan fuentes, **Then** hay exactamente una entrada de pantalla (sin romper el flujo actual).

---

### User Story 2 - Preview matches selected monitor (Priority: P1)

La miniatura de vista previa refleja la pantalla seleccionada (no siempre la primaria).

**Why this priority**: Sin preview correcto, el usuario no sabe qué grabará.

**Independent Test**: Cambiar entre Pantalla 1 y 2 → la preview cambia de contenido/resolución acorde.

**Acceptance Scenarios**:

1. **Given** Pantalla k seleccionada (idle), **When** se refresca la preview, **Then** muestra ese monitor.
2. **Given** se cambia de Pantalla 1 a 2, **When** la preview se actualiza, **Then** deja de mostrar solo la primaria.

---

### User Story 3 - Selection survives refresh (Priority: P2)

Al pulsar Actualizar en fuentes, si el monitor elegido sigue presente, permanece seleccionado; las ventanas siguen listándose como hoy.

**Why this priority**: Paridad con refresh de ventanas (001).

**Independent Test**: Elegir Pantalla 2, Actualizar → sigue Pantalla 2 si existe.

### Edge Cases

- Monitor desconectado tras selección → al refrescar, caer a principal u otra válida.
- Fallback gdigrab (si WGC falla) puede limitarse al escritorio primario — documentar; no bloquear MVP WGC.
- Durante grabación, controles de fuente deshabilitados (comportamiento existente).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST enumerate attached monitors and expose each as a selectable full-screen source.
- **FR-002**: Recording of a screen source MUST target the selected monitor on the primary capture path (WGC).
- **FR-003**: Preview MUST reflect the selected monitor while idle (and recording frames when available).
- **FR-004**: Source refresh MUST preserve monitor selection when that monitor still exists.
- **FR-005**: Single-monitor setups MUST keep a clear full-screen option without requiring extra steps.
- **FR-006**: Window sources MUST continue to work unchanged.

### Key Entities

- **ScreenSource**: A full-screen capture target identified by a stable 1-based monitor index and a user-visible label (primary flag, optional device name/size).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With 2+ monitors, user can record non-primary screen in one selection + record action.
- **SC-002**: Preview for screen sources matches selection within one refresh cycle (~1–2 s).
- **SC-003**: Existing window capture and single-monitor path regress zero in smoke/manual check.

## Assumptions

- WGC `monitor_index` is 1-based and matches `EnumDisplayMonitors` order (windows-capture library).
- gdigrab fallback may not honor secondary monitors; WGC is the supported multi-monitor path.
- No persistence of last monitor across app restarts in MVP (optional later).
