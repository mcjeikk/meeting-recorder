# Research: Transcribe Any Audio File

**Feature**: `009-transcribe-any-file`  
**Date**: 2026-08-17

## Evidence Review (codebase-first)

### E1 — Cómo se transcribe hoy (solo reuniones)

| Claim | Verdict | Sources | Implication |
|-------|---------|---------|-------------|
| Enqueue solo al terminar grabación si checkbox | Confirmed | `main_window._on_finished` | Falta un call site de import |
| Preset + idioma snapshot al encolar | Confirmed | `JobStore.enqueue`, specs 002/003 | Reutilizar; no nueva cola |
| Banner único (progreso/cancel/retry/open/log) | Confirmed | `_tx_banner` | Extender, no duplicar |
| Worker no arranca / suspende si `is_recording()` | Confirmed | `worker._run`, `_monitor` | Import durante grabación = solo enqueue |

### E2 — Extractor vs Transcriptor

| Claim | Verdict | Sources | Implication |
|-------|---------|---------|-------------|
| MP4 Recorder es multipista (Sistema/Mic/Mezcla) | Confirmed | CLAUDE.md, `integration.extract_audio_for_transcription` | Nunca pasar el MP4 crudo al CLI |
| `convertir_a_wav16k` no usa `-map` | Confirmed | Transcriptor `pipeline/audio.py` | Recorder debe extraer primero (ya lo hace el worker) |
| Transcriptor acepta muchos formatos | Confirmed | `AUDIO_EXTS` en `pipeline/audio.py` | Picker/drop deben coincidir con esa lista |
| Resultados: `<parent>/Transcripciones/<stem>/` | Confirmed | `output_dir_for` / `result_dir_for` | Import junto al origen cumple FR-006 sin copiar |

### E3 — Nombres

| Claim | Verdict | Sources | Implication |
|-------|---------|---------|-------------|
| Stem de reunión = título ventana + timestamp | Confirmed | `recording_stem`, `sanitize_filename_component` | Import usa el stem del archivo origen; sanitizar solo si se crea carpeta nueva con nombre sucio (el stem del fichero ya es válido en Windows) |
| Dedupe por `media_path` (normcase) | Confirmed | `JobStore.find_by_media` | Done/active → no segundo job; hoy el post-grabación ignora el `None` en silencio |

### E4 — UX desktop (transcripción desde archivo)

Patrones consistentes en apps locales (Transkrip, Steno/import audio, transcribers Electron):

- Acción **visible**: “Import / Transcribe file…”, no solo menú.
- **Picker + drop** en la ventana (overlay al arrastrar).
- **Mismos settings** (modelo/idioma) y **misma cola/progreso**.
- **No mover** el archivo original.
- Drop a pantalla completa; validar tipo; no procesar carpetas recursivamente en v1.
- Algunos productos **bloquean** import durante grabación. Aquí la constitución pide ceder CPU, no prohibir encolar: **permitir enqueue**, worker ya cede.

**Decisión de producto**: botón en el grupo 4 (Carpeta de salida / transcripción) + hint; drop en toda la ventana; errores en `_status_label` o banner, no modal que pise la grabación.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| D1 Superficie | Extender panel/cola existentes | Spec FR-015; un usuario; banner ya existe |
| D2 Copia del original | No copiar a Grabaciones | Evita duplicar vídeos grandes y mezclar media personal con reuniones |
| D3 Resultados | `result_dir_for(origen)` | Ya implementado; “Abrir” funciona |
| D4 Duplicado done | Informar + abrir | Mejor que el no-op silencioso de `_on_finished` |
| D5 Multi-archivo | Encolar todos los válidos | Power user; worker secuencial |
| D6 Overlay drop | Overlay ligero en drag | Convención desktop; no ventana nueva |
| D7 Transcriptor | Sin cambios | Worker ya extrae WAV 16 kHz y llama CLI |
| D8 Errores | In-window no modal | FR-008 / grabación no se interrumpe |
| D9 Helper | `import_media.py` sin Qt | Tests de classify/enqueue sin GUI |

## Alternatives rejected

- Ventana/wizard de import aparte: oculta el progreso y duplica preset/idioma.
- Copiar media a `%LOCALAPPDATA%` o Grabaciones: I/O pesado; OneDrive ya se mitiga extraendo WAV al work dir.
- Pasar el archivo crudo a `transcribe.py`: rompe MP4 multipista (CLAUDE.md).
- Bloquear import durante grabación (StenoAI): choca con el pedido explícito de encolar mientras se graba.
- Recursión de carpetas: fuera de alcance; mensaje claro si sueltan una carpeta.
- Segundo motor / LLM: constitución II y V.

## Open items for implement (non-blocking)

- Texto exacto del hint en español (corto, junto al botón).
- Filtro del `QFileDialog`: “Audio y vídeo” + “Todos los archivos” con las extensiones de D1/E2.
