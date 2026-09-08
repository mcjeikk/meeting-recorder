# Implementation Plan: Selected Recordings Folder for Conversion Outputs

**Branch**: `010-selected-folder-outputs` | **Date**: 2026-08-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/010-selected-folder-outputs/spec.md`

## Summary

Al cambiar **Carpeta de salida**, las grabaciones nuevas y sus transcripciones visibles deben ir a esa carpeta. Hoy el picker solo actualiza el campo de texto (el `config.json` se guarda al grabar) y `--output` del Transcriptor se une a la raíz del proyecto hermano si la ruta es relativa, de modo que las “conversiones” aparecen en `Transcriptor/…` o en la carpeta anterior. El arreglo es persistir y resolver la carpeta a una ruta absoluta en el momento de elegirla, y pasar siempre `--output` absoluto derivado del MP4 (padre/`Transcripciones`). WAV/cola/logs siguen en `%LOCALAPPDATA%`. Imports (009) siguen junto al origen.

## Technical Context

**Language/Version**: Python 3.11.9 (Recorder `.venv`)

**Primary Dependencies**: PySide6 (`QFileDialog`); `AppConfig` / `RecordingSettings`; `output_dir_for` / `build_command`; Transcriptor CLI vía subproceso (lista de args, **sin** `shell=True`). No fusionar venvs. No hace falta parchear Transcriptor si `--output` es siempre absoluta (pathlib: `RAIZ / abs_path` = `abs_path`).

**Storage**: `%APPDATA%\MeetingRecorder\config.json` (`output_dir` absoluto); cola/logs/WAV de trabajo en `%LOCALAPPDATA%\MeetingRecorder\transcripts\`; MP4 + `Transcripciones/<stem>/` bajo la carpeta seleccionada

**Testing**: unittest (resolver carpeta, `output_dir_for` / `result_dir_for` / `build_command` tras cambiar destino, enqueue con path absoluto). Sin abrir dispositivos de audio. Headless UI no obligatorio si el helper de persistencia es testable sin Qt.

**Target Platform**: Windows desktop

**Project Type**: desktop-app + sibling CLI integration

**Performance Goals**: elegir carpeta y verla aplicada (UI + config) de inmediato; sin impacto en ASR

**Constraints**: Constitution I–V; grabación manda; work files fuera de OneDrive; nunca MP4 multipista crudo al conversor del Transcriptor; no copiar imports a Grabaciones; no fallback silencioso a `~/Videos/Grabaciones`

**Scale/Scope**: un usuario; un campo Carpeta de salida; helpers de resolución de paths; tests focalizados; sin perfiles por proyecto

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Recording Always Wins | PASS | No toca el worker de CPU; carpeta de una grabación en curso no se redirige |
| II. Privacy Is Local by Default | PASS | Sin nube / LLM |
| III. Transcription Stays a Sibling Subprocess | PASS | Sigue CLI + cola; Transcriptor intacto si `--output` es absoluta |
| IV. Paths and Processes Must Be Robust | PASS | Absolutos en lista de args; cola/WAV fuera de sync; carpeta de usuario puede ser OneDrive |
| V. Simplicity for a Single Power User | PASS | Persistencia al elegir + resolve; sin segundo destino ni copias |

**Gate result (pre-design)**: PASS  
**Gate result (post-Phase 1)**: PASS

## Project Structure

### Documentation (this feature)

```text
specs/010-selected-folder-outputs/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── ui-output-folder.md
└── tasks.md
```

### Source Code (repository root)

```text
app/
├── core/config.py                 # resolve_output_dir; persist output_dir absoluto
├── ui/main_window.py              # _choose_output guarda al instante; _build_settings resuelve
├── transcription/
│   ├── integration.py             # output_dir_for / result_dir_for absolutos
│   └── jobs.py                    # enqueue canoniza media_path
tests/
└── test_selected_folder_outputs.py
```

**Structure Decision**: Helpers de path en `config.py` + `integration.py` (testables sin Qt). UI solo persiste al elegir. Transcriptor no se modifica.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Implementation Approach

1. **`resolve_output_dir(raw)`** en `config.py`: `Path(raw).expanduser().resolve()` (si falla, absoluto o `cwd / raw` — no `default_output_dir()`).
2. **`_choose_output`**: si el usuario confirma una carpeta, resolver, pintar el campo, `self._config.output_dir = …`, `save()` **sin** esperar a Grabar.
3. **`_build_settings`**: `output_dir=resolve_output_dir(self._out_edit.text())` para que el MP4 no se escriba relativo al CWD.
4. **`output_dir_for` / `result_dir_for`**: padre del media **resuelto** + `Transcripciones` / stem. `build_command` ya pasa `str(out_dir)`; debe ser absoluta para que Transcriptor no haga `RAIZ / relativo`.
5. **`JobStore.enqueue`**: guardar `canonical_media_path` (o equivalente) para que jobs y `--output` no dependan del CWD.
6. **No** redirigir jobs ya encolados; **no** copiar imports a la carpeta de grabaciones; **no** mover MP4 antiguos.
7. **Tests**: tras “cambiar” a una carpeta B distinta del default, settings.output_dir, `output_dir_for(mp4_en_B)` y `--output` del comando caen bajo B (no default, no LOCALAPPDATA, no relativa a Transcriptor).
