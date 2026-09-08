# Data Model: Transcribe Any Audio File

## TranscriptionJob (unchanged schema)

Jobs siguen siendo JSON en `%LOCALAPPDATA%\MeetingRecorder\transcripts\queue\{id}.json`.

No se añade campo `origin` en MVP: el path y `media_name` bastan para la UI. Un import y una reunión son el mismo tipo de trabajo.

| Field | Import semantics |
|-------|------------------|
| `media_path` | Ruta absoluta del archivo **original** (no se mueve) |
| `language` / `preset` / `model` / `beam_size` / `no_diarize` | Snapshot al encolar, igual que reuniones |
| `log_path` | `{stem}_{id}.log` en `logs/` (stem del origen) |
| `work_wav` | `%LOCALAPPDATA%\...\work\{job_id}\{stem}.wav` |
| `result_dir` | `{parent_del_origen}/Transcripciones/{stem}/` vía `result_dir_for` |
| `status` | Misma máquina de estados (`pending` → `extracting` → `running` → `done`/`error`/`cancelled`) |

### Identity / uniqueness

`find_by_media` compara `os.path.normcase(media_path)`.

| Existing job | Import action |
|--------------|---------------|
| pending / extracting / running | No enqueue; informar “ya en cola” |
| done | No enqueue; informar + permitir Abrir `result_dir` |
| error / cancelled | `enqueue` actual ya permite un job nuevo si el anterior no está active/done (si el JSON error sigue, `find_by_media` lo encuentra y **no** está en `_ACTIVE` ni `DONE` → enqueue crea otro). Implement: si hay job error/cancelled para el mismo path, reutilizar `retry` si error, o enqueue nuevo tras clear — **preferir `retry` si status==error**; si cancelled, permitir enqueue (el store actual crea job nuevo porque cancelled no bloquea). Documentar y testear el comportamiento real de `enqueue`. |

**Store today**: `enqueue` returns `None` iff existing is `_ACTIVE` or `DONE`. Error/cancelled → new job allowed (second JSON). Acceptable; UI should still avoid confusing duplicates by preferring retry on error.

## ImportClassification (ephemeral, not persisted)

Returned by `classify_import` per path:

| Kind | Meaning |
|------|---------|
| `ok` | Encolable |
| `unsupported` | Extensión / carpeta no admitida |
| `missing_file` | Path inexistente |
| `missing_tool` | Transcriptor no disponible |
| `already_active` | Job activo para ese path |
| `already_done` | Job done; incluir `result_dir` si existe |

## User Configuration

Sin campos nuevos. Se reutilizan `transcription_preset`, `transcription_language`, `transcribe_after_recording`.

## UI state (ephemeral)

- Botón **Transcribir archivo…** enabled iff sibling tool available (mismo criterio que checkbox/presets).
- Overlay de drop visible solo durante `dragEnter`/`dragLeave` con files.
- Feedback de import: `_status_label` y/o `_tx_banner` (último job emitido).
- Grabación en curso no deshabilita el botón ni el drop.
