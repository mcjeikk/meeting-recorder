# Feature Specification: Device Hotplug Auto-Refresh

**Feature Branch**: `004-device-hotplug`

**Created**: 2026-07-28

**Status**: Draft

**Input**: User description: "Auto-refresh de dispositivos de captura cuando Windows reporta llegada/salida de hardware (hotplug), como seguimiento natural del refresh manual de micrófonos (001). Respetar Recording Always Wins: nunca reinicializar PortAudio a mitad de grabación."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Micrófono aparece solo al conectar (Priority: P1)

El usuario tiene la app abierta (sin grabar). Empareja o enchufa un micrófono
(Bluetooth Hands-Free / USB). Sin pulsar **Actualizar**, en pocos segundos el
selector de micrófono incluye el nuevo dispositivo y puede elegirlo; el medidor
sigue funcionando.

**Why this priority**: El refresh manual de 001 ya funciona; el dolor restante
es olvidar pulsar Actualizar (especialmente con BT que tarda en exponer HFP).

**Independent Test**: App idle, conectar un mic conocido, esperar ≤ ~5 s sin
tocar Actualizar → el nombre aparece en el combo y se puede seleccionar.

**Acceptance Scenarios**:

1. **Given** la app abierta en idle con lista de mics A, **When** el usuario
   conecta el micrófono B y Windows lo publica como entrada, **Then** B aparece
   en el selector sin reiniciar la app ni pulsar Actualizar.
2. **Given** un auto-refresh que añade B, **When** el usuario selecciona B,
   **Then** el medidor refleja el nuevo dispositivo en pocos segundos.
3. **Given** el botón Actualizar de 001 sigue visible, **When** el usuario lo
   pulsa tras un auto-refresh, **Then** el comportamiento manual existente no
   se rompe (paridad / regresión).

---

### User Story 2 - Desconexión y selección conservada (Priority: P2)

Si el micrófono seleccionado se desconecta en idle, la lista se actualiza y la
UI cae a una opción válida («Sin micrófono» u otro mic aún presente) con un
mensaje breve de estado. Si el mic seleccionado sigue disponible tras un
hotplug de *otro* dispositivo, permanece seleccionado.

**Why this priority**: Evita dejar un mic fantasma seleccionado y no “saltar”
la elección del usuario cuando solo cambia otro dispositivo.

**Independent Test**: Seleccionar mic A; conectar B → A sigue seleccionado.
Desconectar A → A desaparece y el selector no apunta a un nombre inválido.

**Acceptance Scenarios**:

1. **Given** mic A seleccionado, **When** se conecta B y ocurre auto-refresh,
   **Then** A sigue seleccionado si sigue disponible.
2. **Given** mic A seleccionado, **When** se desconecta A y ocurre auto-refresh,
   **Then** A ya no está en la lista (o no es seleccionable) y hay alternativa
   válida o «Sin micrófono», con feedback de estado.
3. **Given** ráfagas de eventos de Windows al conectar BT, **When** llegan
   varios avisos en <1 s, **Then** la UI no parpadea de forma molesta (un
   refresh consolidado basta).

---

### User Story 3 - Grabación no se corta por hotplug (Priority: P1)

Durante una grabación activa, un plug/unplug de dispositivos **no** reinicia
el motor de audio ni detiene la captura. El auto-refresh con reinicio de lista
profunda queda aplazado hasta idle (o se omite el reinicio profundo); el
usuario puede seguir usando Actualizar manual sin PortAudio reinit mid-recording
(comportamiento 001).

**Why this priority**: Constitution — Recording Always Wins; un refresh agresivo
a mitad de reunión es peor que una lista momentáneamente stale.

**Independent Test**: Iniciar grabación corta; conectar/desconectar un mic USB
o BT → la grabación continúa; al detener, en idle el auto-refresh (o Actualizar)
muestra la lista al día.

**Acceptance Scenarios**:

1. **Given** grabación en curso, **When** Windows reporta llegada/salida de
   dispositivo de audio, **Then** la grabación no se detiene ni pierde pistas.
2. **Given** grabación en curso y un mic recién conectado, **When** el usuario
   mira el selector, **Then** puede que el nuevo mic aún no aparezca hasta
   idle/Actualizar profundo — aceptable; no hay crash ni corte de audio.
3. **Given** grabación que acaba de terminar, **When** había eventos diferidos
   o un nuevo plug en idle, **Then** la lista se actualiza sin intervención
   (o tras un breve debounce).

---

### Edge Cases

- Bluetooth que primero aparece como Stereo (solo salida) y luego Hands-Free:
  el auto-refresh puede necesitar más de un ciclo; el usuario aún puede pulsar
  Actualizar.
- Eventos de dispositivo no-audio (USB storage, etc.): no deben forzar refrescos
  constantes ni reinicios de PortAudio.
- App minimizada / sin foco: el auto-refresh sigue aplicándose a la lista.
- Fallo al reiniciar el motor de audio en idle: best-effort; conservar lista
  previa y no tumbar la app; Actualizar manual sigue disponible.
- Cambio de ventana/monitor (fuentes de video): fuera de alcance de este feature
  (sigue el botón Actualizar de fuentes).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: En idle, el sistema MUST actualizar la lista de micrófonos cuando
  Windows indica que un dispositivo de audio relevante llegó o se fue, sin
  exigir reinicio de la app.
- **FR-002**: El auto-refresh en idle MUST reutilizar la misma política de
  identidad/selección que el refresh manual (conservar por nombre exacto;
  fallback «Sin micrófono»).
- **FR-003**: Durante grabación, el sistema MUST NOT reinicializar el motor de
  audio de captura de micrófono / keep-alive de forma que corte la grabación.
- **FR-004**: Eventos de hotplug durante grabación MUST diferir el refresh
  profundo hasta idle, u omitirlo sin romper la captura; el botón Actualizar
  de micrófonos permanece con la semántica de 001.
- **FR-005**: Ráfagas de notificaciones MUST consolidarse (debounce) en un
  número acotado de refrescos de UI.
- **FR-006**: Tras un auto-refresh que cambia la lista, el sistema MUST dar
  feedback breve de estado cuando hay altas, bajas o pérdida de selección
  (paridad razonable con mensajes de 001).
- **FR-007**: El refresh manual de micrófonos MUST seguir disponible y correcto
  (no sustituido ni eliminado).
- **FR-008**: Fuentes de video (ventanas / pantalla) NO son objeto de auto-
  refresh por hotplug de audio en este feature.

### Key Entities

- **Micrófono listado**: dispositivo de entrada visible en el selector (nombre
  como identidad).
- **Evento de cambio de dispositivo**: señal del SO de que el conjunto de
  endpoints de audio pudo cambiar.
- **Modo grabación vs idle**: determina si se permite refresh profundo.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En idle, un micrófono USB o BT Hands-Free ya expuesto por Windows
  aparece en el selector en ≤ 5 segundos tras la notificación del SO, sin
  pulsar Actualizar, en ≥ 8 de 10 pruebas manuales.
- **SC-002**: En 10 grabaciones de prueba con plug/unplug durante la captura,
  0 se detienen o pierden la pista de audio por culpa del auto-refresh.
- **SC-003**: Tras conectar un segundo mic en idle con otro ya seleccionado, la
  selección previa se conserva en ≥ 9 de 10 casos si el dispositivo sigue
  listado.
- **SC-004**: El usuario no necesita reiniciar la app para ver un mic nuevo en
  el escenario idle estándar (mismo valor que 001, ahora sin acción manual).

## Assumptions

- El refresh manual de 001 (incl. reinicio profundo de lista en idle) es la
  base reutilizable; este feature solo dispara esa ruta automáticamente.
- Identidad de micrófono = nombre exacto mostrado (igual que 001).
- Windows puede retrasar la aparición del perfil Hands-Free de BT; un segundo
  refresh o Actualizar manual sigue siendo válido.
- Un único usuario en escritorio Windows; no hace falta UI de configuración
  on/off en MVP (siempre activo).
- No se añade dependencia de servicios cloud ni de enumeración continua agresiva
  (polling de alta frecuencia).
- Auto-refresh de monitores/ventanas queda fuera de alcance (backlog aparte).
