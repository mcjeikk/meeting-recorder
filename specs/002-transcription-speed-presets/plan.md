# Implementation Plan: Transcription Speed Presets

**Branch**: `002-transcription-speed-presets` | **Date**: 2026-07-27 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-transcription-speed-presets/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Exponer en la UI del Recorder tres presets de transcripción (**Rápido / Equilibrado / Máxima calidad**) que se persisten en `AppConfig`, se capturan en cada `TranscriptionJob` al encolar, y se traducen a flags CLI del proyecto hermano Transcriptor (`--model`, `--beam-size`, `--no-diarize`) vía el worker existente (`build_command` + `extra_args`). **Fase 1** = UI + job snapshot + CLI mapping. **Fase 2** (planificada, no bloqueante) = reutilización de carga de modelo en el lado Transcriptor sin fusionar venvs ni romper Recording Always Wins.

## Technical Context

**Language/Version**: Python 3.11.9 (Recorder `.venv`; Transcriptor sibling `.venv` unchanged / separate)

**Primary Dependencies**: PySide6 (UI); cola durable JSON; Transcriptor CLI (`transcribe.py`) via subprocess

**Storage**: `%APPDATA%\MeetingRecorder\config.json` (preset preferido); `%LOCALAPPDATA%\MeetingRecorder\transcripts\queue\*.json` (preset/params por job)

**Testing**: headless UI (`QT_QPA_PLATFORM=offscreen`, `MainWindow` sin `show()`); unit tests de mapping preset→CLI; `verify_transcription.py --quick` con preset Rápido si aplica; manual ordering check SC-002

**Target Platform**: Windows desktop

**Project Type**: desktop-app + sibling CLI integration

**Performance Goals**: Rápido &lt; Equilibrado ≤ Máxima calidad en wall-clock sobre la misma muestra corta (SC-002); Phase 2 apunta a reducir tiempo de init de modelo en jobs consecutivos same-preset

**Constraints**: Constitution I–V; no fused venv; no cloud upload; no LLM; Recording Always Wins; job snapshot immutable after enqueue; Phase 2 optional

**Scale/Scope**: un usuario; un control de preset + hint; tres mappings fijos; cambios en Recorder (+ opcional Transcriptor en Phase 2)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Recording Always Wins | PASS | Presets no cambian suspend/priority/`--threads cpu-2`; worker sigue sin arrancar si `is_recording()`. |
| II. Privacy Is Local by Default | PASS | Solo flags locales al CLI hermano; sin upload. |
| III. Transcription Stays a Sibling Subprocess | PASS | Fase 1 solo pasa CLI args. Fase 2 (si existe) mantiene proceso/entorno separado — p. ej. daemon/warmup *dentro* de Transcriptor, nunca importar torch en Recorder. |
| IV. Paths and Processes Must Be Robust | PASS | Sigue `build_command` con lista de args; cola fuera de OneDrive. |
| V. Simplicity for a Single Power User | PASS | Tres presets fijos; sin panel avanzado de hiperparámetros en MVP. |

**Gate result (pre-design)**: PASS

**Gate result (post-Phase 1)**: PASS — contratos UI + job + CLI; Phase 2 documentada como sibling-side only.

## Project Structure

### Documentation (this feature)

```text
specs/002-transcription-speed-presets/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── ui-transcription-presets.md
│   └── cli-preset-mapping.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
app/
├── ui/
│   └── main_window.py           # combo/radio preset + hint; save/load; enqueue usa preset
├── core/
│   └── config.py                # AppConfig.transcription_preset
├── transcription/
│   ├── jobs.py                  # TranscriptionJob: preset + model/beam/no_diarize fields
│   ├── worker.py                # enqueue(…, preset); _execute builds extra from job
│   ├── presets.py               # NUEVO: mapping preset → CLI params (fuente única)
│   └── integration.py           # build_command ya acepta extra_args (sin cambio de firma obligatorio)
# Sibling (Phase 2 only, optional):
../Transcriptor/
├── pipeline/asr.py              # posible cache in-process si hubiera worker largo
└── (futuro warm daemon — solo si Phase 2 se implementa)
```

**Structure Decision**: Extender el pipeline de cola/worker del Recorder. Un módulo pequeño `presets.py` concentra el mapping para UI, jobs y tests. Transcriptor solo cambia en Phase 2.

## Complexity Tracking

> Sin violaciones — tabla vacía.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Implementation Approach (guidance for `/speckit-tasks`)

### Phase 1 (ship)

1. **`presets.py`**: enum/constantes `rapido|equilibrado|maxima_calidad` + labels ES + hint text + `to_cli_args()` → `--model`, `--beam-size`, optional `--no-diarize`.
2. **Mappings (research-locked after evidence review)**:
   - Rápido: `large-v3-turbo`, beam `1`, `--no-diarize` (speed from no speakers + greedy decode; **not** `medium` — turbo is faster than medium)
   - Equilibrado: `large-v3-turbo`, beam `5`, diarize on (omit flag)
   - Máxima calidad: `large-v3`, beam `5`, diarize on
3. **`AppConfig.transcription_preset`**: default `equilibrado`; load/save; unknown → equilibrado.
4. **`TranscriptionJob`**: store `preset` string + optionally denormalized `model`, `beam_size`, `no_diarize` for forward-compat; capture at enqueue; retry keeps fields.
5. **Worker `_execute`**: append preset CLI args; if degraded retry sets `no_diarize=True`, that still wins over preset’s diarize-on (existing recovery).
6. **UI**: control cerca del checkbox “Transcribir al terminar”; hint dinámico; persist on change; disabled semantics: selectable anytime (does not affect in-flight jobs).
7. **Tests**: mapping unit tests; headless MainWindow load/save preset; optional quick verify with Rápido.

### Phase 2 (plan only until implement)

**OUT OF SCOPE for `/speckit-implement` of Phase 1 (US1–US3).** Do **not** implement a Transcriptor daemon, model cache process, or any Recorder-side torch import unless the user explicitly confirms Phase 2 implement.

- Prefer **Transcriptor-side** warm process holding `WhisperModel` / CTranslate2 instance in memory between jobs, or in-process model cache if a long-lived sibling worker is introduced — **not** importing models into Recorder (see research E4).
- Alternative rejected: fused venv / in-process Whisper in Recorder (constitution III).
- Alternative deferred: always-on scheduled Windows task (constitution V).
- Document measurement: cold vs warm second job same preset (model-init wall time) — see quickstart Phase 2 section.
- Realistic Phase 2: optional sibling daemon with stdin/socket protocol; Recorder still owns durable queue and Recording Always Wins (refuse spawn / suspend child). Skip Phase 2 code unless user explicitly requests it.

#### Phase 2 approach options (sibling-only)

| Option | Description | Verdict |
|--------|-------------|---------|
| A. Long-lived Transcriptor worker | Process in Transcriptor `.venv` keeps `WhisperModel` loaded; Recorder connects via socket/named pipe/stdin protocol preserving preset→CLI semantics | Preferred if measured cold-start waste justifies it |
| B. In-process cache in one-shot CLI | Cache only helps if one invocation processes a batch; current design is one-file-per-job | Limited value today |
| C. Accept cold start | Document and close as wontfix / revisit | Valid for single power user (constitution V) |

**Rejected**: fuse torch into Recorder venv; Windows Scheduled Task mega-worker.

**Measurement (when Phase 2 is implemented)**: same short sample, same preset, two consecutive jobs — compare wall-clock from process start to first ASR progress (cold vs warm). Confirm Recording Always Wins still suspends/yields the sibling child.

> **2026-07-28 update**: Phase 2 code remains deferred. Refined decision and backlog unlock live in [`specs/005-model-load-reuse/`](../005-model-load-reuse/deferral.md) (docs only; no daemon this pass).
