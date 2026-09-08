# Implementation Plan: Transcribe Any Audio File

**Branch**: `009-transcribe-any-file` | **Date**: 2026-08-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/009-transcribe-any-file/spec.md`

## Summary

Añadir una acción de primer nivel **Transcribir archivo…** (selector + arrastrar y soltar) en la ventana principal para encolar audio/vídeo existente en la **misma** cola durable de transcripción que las reuniones. Reutiliza presets, idioma, banner (progreso / cancelar / reintentar / abrir / log). El archivo original no se mueve; el WAV de trabajo sigue en `%LOCALAPPDATA%`; los resultados van a `<carpeta del origen>/Transcripciones/<stem>/`. Grabar sigue teniendo prioridad de CPU.

## Technical Context

**Language/Version**: Python 3.11.9 (Recorder `.venv`)

**Primary Dependencies**: PySide6 (UI, `QFileDialog`, drag-and-drop); `JobStore` + `TranscriptionWorker`; ffmpeg via `extract_audio_for_transcription`; Transcriptor CLI (`transcribe.py`) via subprocess — **no** se fusionan venvs ni se cambia Transcriptor salvo que resulte estrictamente necesario (no se espera)

**Storage**: cola JSON en `%LOCALAPPDATA%\MeetingRecorder\transcripts\queue\`; WAV de trabajo en `...\work\`; resultados junto al archivo origen; `config.json` sin campos nuevos (preset/idioma existentes)

**Testing**: unittest (validación de extensiones, clasificación import vs duplicado, enqueue); headless UI opcional (`QT_QPA_PLATFORM=offscreen`, no `show()`)

**Target Platform**: Windows desktop

**Project Type**: desktop-app + sibling CLI integration

**Performance Goals**: elegir/soltar un archivo y verlo en cola en &lt; 5 s (SC-004); ASR sin claims nuevos; import durante grabación no detiene captura (SC-005)

**Constraints**: Constitution I–V; lista de argumentos nunca `shell=True`; nunca pasar MP4 multipista crudo a `convertir_a_wav16k` del Transcriptor (siempre extraer Mezcla/única/amix en Recorder); no copiar el original a Grabaciones; errores in-window no modales

**Scale/Scope**: un usuario; un botón + drop en la ventana; helper de import testable; sin dashboard de historial ni ventana nueva

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Recording Always Wins | PASS | Encolar permitido durante grabación; worker ya no arranca / suspende (`is_recording`) |
| II. Privacy Is Local by Default | PASS | Sin subida a la nube; sin LLM |
| III. Transcription Stays a Sibling Subprocess | PASS | Misma cola + `transcribe.py`; no importar torch |
| IV. Paths and Processes Must Be Robust | PASS | Paths absolutos en lista; WAV/cola fuera de OneDrive; origen puede estar en sync (sin copiar el original) |
| V. Simplicity for a Single Power User | PASS | Extiende panel/cola existentes; un helper; sin segundo motor ni ventana |

**Gate result (pre-design)**: PASS  
**Gate result (post-Phase 1)**: PASS

## Project Structure

### Documentation (this feature)

```text
specs/009-transcribe-any-file/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── ui-transcribe-file.md
└── tasks.md
```

### Source Code (repository root)

```text
app/
├── ui/main_window.py                 # botón, picker, drop, overlay, mensajes in-window
├── core/config.py                    # reutilizar sanitize_filename_component si hace falta el stem
├── transcription/
│   ├── import_media.py               # NUEVO: extensiones, classify/enqueue import (sin Qt)
│   ├── integration.py                # extraer audio (ya correcto para multipista)
│   ├── jobs.py                       # find_by_media / enqueue existentes
│   └── worker.py                     # enqueue existente; copy "archivo ya no existe"
tests/
└── test_transcribe_any_file.py
```

**Structure Decision**: Un módulo nuevo delgado `import_media.py` (lógica testable sin Qt). UI solo orquesta. Worker/extractor existentes cubren el pipeline. Transcriptor no se modifica.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Implementation Approach

1. **`SUPPORTED_MEDIA_EXTS`**: mismo conjunto que Transcriptor `AUDIO_EXTS` (mp3, m4a, wav, flac, ogg, opus, aac, wma, mp4, m4b, mkv, webm, mov, avi).
2. **`classify_import(store, path, tool_available)`** → `ok` / `unsupported` / `folder` / `missing_file` / `missing_tool` / `already_active` / `already_done` (con `result_dir` si done).
3. **`enqueue_imports(...)`**: para cada path absoluto, classify; si `ok`, `worker.enqueue` con preset/idioma actuales; devolver lista de resultados para la UI.
4. **UI**: botón **Transcribir archivo…** en el grupo 4 (junto a checkbox/presets/idioma) + hint; `QFileDialog.getOpenFileNames`; `setAcceptDrops`; overlay ligero al arrastrar; `_status_label` / banner de transcripción para feedback (nunca `QMessageBox` que bloquee grabación).
5. **Duplicado done**: no re-encolar; mensaje + **Abrir** si hay `result_dir`.
6. **Extractor**: sin cambios de algoritmo; `extract_audio_for_transcription` ya elige Mezcla / única / amix. Ajustar texto de error del worker si dice “grabación” para que sirva también a imports.
7. **Tests**: extensiones; classify duplicados; enqueue de path arbitrario; no copiar el original.
