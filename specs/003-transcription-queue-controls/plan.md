# Implementation Plan: Transcription Queue Controls

**Branch**: `003-transcription-queue-controls` | **Date**: 2026-07-27 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-transcription-queue-controls/spec.md`

## Summary

Extender la UI/cola de transcripción del Recorder con tres controles MVP: **Cancelar** job pendiente o activo, **selector de idioma** (`es`/`en`/`auto`) persistido, y **limpiar fallidos/cancelados** de la cola durable. Reutiliza el banner existente (progreso / Reintentar / Abrir / Ver log). Sin panel de historial completo.

## Technical Context

**Language/Version**: Python 3.11.9 (Recorder `.venv`)

**Primary Dependencies**: PySide6 (UI); `JobStore` + `TranscriptionWorker`; Transcriptor CLI via subprocess; `psutil` (ya usado para suspend/monitor)

**Storage**: `%APPDATA%\MeetingRecorder\config.json` (`transcription_language`); `%LOCALAPPDATA%\MeetingRecorder\transcripts\queue\*.json`

**Testing**: unit tests de `JobStore.cancel` / `clear_failed` (+ normalize language); headless UI smoke opcional; quickstart manual

**Target Platform**: Windows desktop

**Project Type**: desktop-app + sibling CLI integration

**Performance Goals**: Cancel detiene trabajo del job en ≤ ~15 s (SC-002); sin claims de velocidad de ASR

**Constraints**: Constitution I–V; no fused venv; no cloud; Recording Always Wins; language snapshot at enqueue; no history dashboard

**Scale/Scope**: un usuario; controles en banner + fila de idioma junto a presets

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Recording Always Wins | PASS | Cancel/clear no bloquean grabación; no cambian suspend/priority |
| II. Privacy Is Local by Default | PASS | Solo UI/cola local |
| III. Transcription Stays a Sibling Subprocess | PASS | Cancel termina el hijo CLI; no se importa torch |
| IV. Paths and Processes Must Be Robust | PASS | Args list intactos; cola en LocalAppData |
| V. Simplicity for a Single Power User | PASS | Tres acciones; sin dashboard de historial |

**Gate result (pre-design)**: PASS  
**Gate result (post-Phase 1)**: PASS

## Project Structure

### Documentation (this feature)

```text
specs/003-transcription-queue-controls/
├── plan.md
├── research.md
├── data-model.md
├── validation.md
├── quickstart.md
├── contracts/
│   ├── ui-queue-controls.md
│   └── job-cancel-clear.md
└── tasks.md
```

### Source Code (repository root)

```text
app/
├── ui/main_window.py              # idioma combo; botones Cancelar / Limpiar fallidos
├── core/config.py                 # normalize language on load/save (si hace falta)
├── transcription/
│   ├── jobs.py                    # CANCELLED; cancel(); clear_failed(); delete
│   └── worker.py                  # cancel(job_id); honor flag en _monitor; clear_failed API
tests/
└── test_transcription_queue_controls.py
```

**Structure Decision**: Extender jobs/worker/UI existentes; sin módulos nuevos salvo tests.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Implementation Approach

1. **`CANCELLED` status** + `JobStore.cancel(job_id)` + `clear_failed()` (borra JSON error/cancelled).
2. **`TranscriptionWorker.cancel(job_id)`**: marca cancel; si `_current`/`pid` owned → `terminate`/`kill` best-effort; `_monitor` sale al ver proceso muerto y `_settle` respeta cancel antes de retry automático.
3. **UI**: combo Idioma (`Español`/`English`/`Auto`); botón Cancelar visible en pending/extracting/running; Limpiar fallidos cuando haya error/cancelled en store o en banner.
4. **Language normalize**: `es|en|auto`, default `es`.
5. **Tests**: cancel pending; clear_failed leaves pending/done; normalize language.
