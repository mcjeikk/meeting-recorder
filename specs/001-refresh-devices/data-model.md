# Data Model: Refresh Capture Devices

**Feature**: `001-refresh-devices`  
**Date**: 2026-07-27

Entidades conceptuales del spec; en código mapean a tipos existentes en `app/core/config.py` y estado de `MainWindow`. **No se introducen tablas ni persistencia nueva** salvo el uso opcional del `last_mic_name` ya existente al arranque.

## Entities

### VideoSource (fuente de video)

| Field | Type | Notes |
|-------|------|-------|
| `kind` | `"screen"` \| `"window"` | Pantalla completa vs ventana |
| `title` | `str` | Título visible; clave de match al refrescar ventanas |
| `hwnd` | `int \| None` | Handle Windows; puede cambiar si la ventana se recrea — match de UI por título |

**UI representation**: ítem en `_source_combo` — “Pantalla completa” (`userData=None`) o “🪟 {title}” (`userData=VideoSource`).

**Validation**:
- Tras refresh, si `kind == "window"` y el título sigue en la lista → conservar índice.
- Si era pantalla completa (`prev` no es `VideoSource`) → permanecer en índice 0.
- Si la ventana desapareció → el combo queda en el ítem por defecto del Qt tras `clear`/repopulate (típicamente pantalla completa); no se exige diálogo.

### AudioDevice (dispositivo de micrófono)

| Field | Type | Notes |
|-------|------|-------|
| `index` | `int` | Índice sounddevice/WASAPI; **no** usar como identidad estable |
| `name` | `str` | Nombre visible; **clave de identidad** para conservar selección (FR-003) |
| `channels` | `int` | Formato nativo |
| `sample_rate` | `int` | Formato nativo |

**Sentinel**: `None` / ítem “Sin micrófono” = sin captura de mic.

**UI representation**: ítem en `_mic_combo` — texto = `name` o “Sin micrófono”.

**Validation**:
- Match post-refresh: igualdad exacta de texto/nombre.
- Si el nombre previo no está → fallback seguro (“Sin micrófono” o primer dispositivo disponible) + mensaje de estado (FR-007).
- Lista vacía de hardware → solo “Sin micrófono”; no crash.

### ActiveSelection (selección activa)

Par lógico (no clase dedicada requerida):

| Field | Type | Notes |
|-------|------|-------|
| `video` | `VideoSource \| screen-sentinel` | Valor actual de `_source_combo` |
| `mic` | `AudioDevice \| None` | Valor actual de `_mic_combo` |

**Invariants**:
- Refresh de mics no altera `video`.
- Refresh de fuentes no altera `mic`.
- Durante grabación, `video` no puede cambiar desde la UI; `mic` sí.

## State transitions

### Mic list refresh (manual)

```text
[Idle or Recording]
       │ user clicks "Actualizar" (mic section)
       ▼
  Capture prev_name (combo text / device.name / "Sin micrófono")
       ▼
  Enumerate list_microphones() → rebuild combo
       ▼
  ┌─ prev_name found? ─yes─► restore selection
  │                         │
  │                         ├─ if not recording → AudioMonitor.set_mic(current)
  │                         └─ if recording → no monitor; mic capture unchanged until user picks another
  │
  └─ no ─► fallback selection + status message
            └─ if not recording → AudioMonitor.set_mic(fallback)
```

### Mic change after refresh (existing path)

```text
User activates combo item
  ├─ recording? → Recorder.change_mic(device)
  └─ idle?      → AudioMonitor.set_mic(device)
```

### Source list refresh (manual, existing)

```text
[Idle only — button disabled while recording]
  → capture prev VideoSource / screen
  → list_windows() → rebuild combo
  → restore by title or keep screen
  → _update_preview()
```

## Relationships

```text
ActiveSelection
  ├── video → VideoSource | screen
  └── mic   → AudioDevice | None

AppConfig.last_mic_name ──(startup only)──► initial mic combo selection
```

## Out of scope for this model

- Identidad hardware estable (GUID/endpoint ID)
- Eventos hotplug
- Historial de mics desaparecidos
- Cambiar `VideoSource` mid-recording
