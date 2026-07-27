# Feature Specification: Refresh Capture Devices

**Feature Branch**: `001-refresh-devices`

**Created**: 2026-07-27

**Status**: Draft

**Input**: User description: "Poder actualizar la lista de micrófonos en determinado momento, igual que ya se actualizan las ventanas/pestañas; mejorar el refresco de fuentes de captura."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Refrescar micrófonos a demanda (Priority: P1)

Antes de grabar (o entre reuniones), el usuario conecta o cambia de micrófono
(auriculares Bluetooth, USB, headset de oficina). Abre el Grabador, pulsa
**Actualizar** junto al selector de micrófono y ve la lista al día, sin
reiniciar la aplicación.

**Why this priority**: Hoy solo se listan micrófonos al arrancar; es el hueco
que el usuario reportó y bloquea elegir el dispositivo correcto.

**Independent Test**: Con la app abierta, conectar o desconectar un micrófono
conocido, pulsar Actualizar en la sección Micrófono y comprobar que la lista
cambia; se puede seleccionar el nuevo dispositivo y el medidor reacciona.

**Acceptance Scenarios**:

1. **Given** la app abierta con un micrófono A en la lista, **When** el usuario
   conecta el micrófono B y pulsa Actualizar en Micrófono, **Then** B aparece
   en el selector y puede elegirse.
2. **Given** el micrófono B seleccionado, **When** el usuario lo desconecta y
   pulsa Actualizar, **Then** B ya no aparece (o queda marcado como no
   disponible) y el selector ofrece una alternativa válida o “Sin micrófono”.
3. **Given** un micrófono seleccionado y el medidor activo, **When** el usuario
   refresca y elige otro micrófono, **Then** el medidor pasa a reflejar el
   nuevo dispositivo en pocos segundos.

---

### User Story 2 - Conservar selección y no romper la grabación (Priority: P2)

Al refrescar, si el micrófono (o la ventana) que el usuario tenía elegido
sigue disponible, permanece seleccionado. Si está grabando, puede refrescar
y cambiar de micrófono; no puede cambiar la fuente de video a mitad de
grabación (comportamiento actual conservado).

**Why this priority**: Un refresh que “salta” al primer dispositivo o
interrumpe la grabación empeora la experiencia más que no tener refresh.

**Independent Test**: Seleccionar un micrófono no por defecto, refrescar sin
cambios físicos → sigue seleccionado. Durante una grabación corta, refrescar
mics y cambiar de mic → la grabación continúa y el audio del mic nuevo entra
en la pista.

**Acceptance Scenarios**:

1. **Given** un micrófono no-default seleccionado y sin cambios de hardware,
   **When** el usuario pulsa Actualizar micrófonos, **Then** ese mismo
   micrófono sigue seleccionado.
2. **Given** una grabación en curso, **When** el usuario refresca micrófonos y
   elige otro, **Then** la grabación no se detiene y el cambio de mic se
   aplica en caliente.
3. **Given** una grabación en curso, **When** el usuario intenta refrescar o
   cambiar la fuente de video (ventana/pantalla), **Then** esos controles
   permanecen deshabilitados / no cambian la fuente activa.

---

### User Story 3 - Refresco de ventanas/pestañas sigue claro (Priority: P3)

El usuario abre una nueva ventana o pestaña de reunión (Teams, navegador).
Pulsa **Actualizar** en “¿Qué quieres grabar?” y la lista incluye la nueva
ventana, conservando la selección previa si sigue abierta.

**Why this priority**: La función ya existe; esta historia asegura paridad de
comportamiento (conservar selección, feedback claro) junto al nuevo refresh
de mics, sin ampliar a cambio de fuente mid-recording.

**Independent Test**: Abrir una ventana con título distintivo, Actualizar
fuentes, seleccionarla y ver vista previa coherente.

**Acceptance Scenarios**:

1. **Given** una nueva ventana de reunión visible, **When** el usuario pulsa
   Actualizar en fuentes, **Then** esa ventana aparece en el selector.
2. **Given** una ventana ya seleccionada que sigue abierta, **When** refresca
   fuentes, **Then** esa ventana permanece seleccionada si aún existe.

---

### Edge Cases

- Refresco mientras el listado de dispositivos está vacío (sin mics): mostrar
  “Sin micrófono” y no fallar.
- Nombre de dispositivo duplicado o que cambia ligeramente tras reconectar
  Bluetooth: preferir coincidencia exacta de nombre; si no hay match, no
  forzar un índice arbitrario sin avisar.
- El micrófono en uso desaparece a mitad de grabación: la grabación MUST
  continuar (pista de silencio o segmento cerrado); el usuario MUST poder
  refrescar y elegir otro mic.
- Refresco muy frecuente: la UI MUST permanecer usable (sin congelarse
  varios segundos).
- App minimizada en bandeja: el refresh manual aplica al volver a mostrar;
  no se exige auto-refresh en bandeja para esta versión.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El usuario MUST poder actualizar la lista de micrófonos con una
  acción explícita en la sección de Micrófono, sin reiniciar la app.
- **FR-002**: El usuario MUST poder actualizar la lista de ventanas/pantalla
  con la acción explícita existente en la sección de fuente.
- **FR-003**: Tras refrescar micrófonos, si el dispositivo previamente
  seleccionado sigue disponible (mismo nombre), el sistema MUST conservar esa
  selección.
- **FR-004**: Tras refrescar fuentes, si la ventana previamente seleccionada
  sigue disponible, el sistema MUST conservar esa selección; si era pantalla
  completa, MUST permanecer en pantalla completa.
- **FR-005**: Tras un refresh de micrófonos fuera de grabación, el monitor de
  nivel MUST usar el micrófono actualmente seleccionado.
- **FR-006**: Durante una grabación, el refresh y cambio de micrófono MUST
  permanecer disponibles; el refresh/cambio de fuente de video MUST permanecer
  bloqueado.
- **FR-007**: Si tras un refresh el micrófono seleccionado ya no existe, el
  sistema MUST seleccionar un fallback seguro (“Sin micrófono” o el primero
  disponible) y comunicar el cambio en el estado de la UI (mensaje breve).
- **FR-008**: Las acciones de refresh MUST completarse de forma que la ventana
  siga respondiendo; si el enumerado tarda, el usuario MUST ver que la acción
  ocurrió (cambio de lista o feedback de estado).

### Key Entities

- **Fuente de video**: pantalla completa o ventana identificada por título
  visible para el usuario.
- **Dispositivo de micrófono**: entrada de audio eligible, identificada por
  nombre visible en el selector.
- **Selección activa**: el par fuente + micrófono (o “sin mic”) que la UI
  considera elegido antes/después de un refresh.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En pruebas manuales, un micrófono conectado tras abrir la app
  aparece en el selector en menos de 3 segundos tras pulsar Actualizar.
- **SC-002**: En al menos 9 de 10 refrescos sin cambio de hardware, la
  selección previa de micrófono se conserva.
- **SC-003**: Un usuario puede pasar de “micrófono viejo en lista” a “grabar
  con el micrófono recién conectado” sin cerrar la aplicación.
- **SC-004**: Refrescar dispositivos no provoca cierre de la app ni detiene
  una grabación en curso.
- **SC-005**: Tras refrescar fuentes, una ventana de reunión nueva es
  seleccionable y su vista previa se actualiza en la misma sesión.

## Assumptions

- El alcance de esta versión es **refresco manual** (botón/acción explícita).
  La detección automática al enchufar/desenchufar (hotplug) queda fuera de
  MVP y puede especificarse después.
- Un solo usuario local; no hay perfiles ni permisos multi-usuario.
- Windows es la plataforma objetivo; el comportamiento en otros SO no forma
  parte de esta feature.
- El cambio de micrófono en caliente durante la grabación ya existe y se
  reutiliza; esta feature añade/asegura el refresco de la lista y la
  conservación de selección.
- No se cambia la fuente de video a mitad de grabación (sigue fuera de
  alcance, como hoy).
- Los nombres de dispositivo que muestra el sistema operativo son la clave
  de identidad para conservar selección.
