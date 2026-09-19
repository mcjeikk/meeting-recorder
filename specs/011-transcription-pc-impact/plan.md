# Implementation Plan: Keep the PC Usable During Transcription

**Branch**: `011-transcription-pc-impact` | **Date**: 2026-09-08 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/011-transcription-pc-impact/spec.md`

## Summary

Transcription freezes the rest of the desktop because Equilibrado/Máxima still run speaker labeling, and torch/OpenMP ignore the existing `--threads cpu-2` cap. Add a persisted **Uso del PC** control (`full` default vs `usable`) independent of quality presets. Snapshot it on each job. `usable` uses a smaller thread budget, IDLE priority, and env/`torch` caps so other apps stay responsive — including with Máxima calidad. Recording Always Wins is unchanged.

## Technical Context

**Language/Version**: Python 3.11.9 (Recorder `.venv`); Transcriptor sibling `.venv` (torch +cpu)

**Primary Dependencies**: PySide6 combo; `AppConfig`; durable `JobStore`; `subprocess.Popen` with `creationflags` + env list (never `shell=True`); Transcriptor `--threads`

**Storage**: `%APPDATA%\MeetingRecorder\config.json` (`transcription_pc_impact`); job JSON in `%LOCALAPPDATA%\MeetingRecorder\transcripts\queue\`

**Testing**: unittest for normalize, thread math, env keys, job snapshot/legacy, creationflags. No real audio devices.

**Target Platform**: Windows desktop

**Project Type**: desktop-app + sibling CLI

**Performance Goals**: usable jobs must request fewer threads than full on >4-core machines; desktop remains the priority, wall-clock may grow

**Constraints**: Constitution I–V; do not fuse venvs; do not drop diarization when the preset asks for speakers; do not change output folders

**Scale/Scope**: one combo + helpers + job field; small Transcriptor honor-`--threads` for torch

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Recording Always Wins | PASS | Suspend-on-record unchanged; usable only throttles a *running* job when not recording |
| II. Privacy Is Local by Default | PASS | Still local sibling CLI |
| III. Transcription Stays a Sibling Subprocess | PASS | Env + existing `--threads`; optional torch cap inside Transcriptor, not a fused library |
| IV. Paths and Processes Must Be Robust | PASS | Argv list; env dict copy |
| V. Simplicity for a Single Power User | PASS | Two named choices, no spinner / job objects |

**Gate result (pre-design)**: PASS  
**Gate result (post-Phase 1)**: PASS

## Project Structure

### Documentation (this feature)

```text
specs/011-transcription-pc-impact/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── ui-pc-impact.md
├── tasks.md
└── checklists/requirements.md
```

### Source Code (repository root)

```text
app/transcription/pc_impact.py          # NEW: ids, normalize, threads, flags, env
app/transcription/integration.py        # cpu_threads_for_job + env/flags use profile
app/transcription/jobs.py               # snapshot pc_impact; legacy → full
app/transcription/worker.py             # launch with job profile
app/core/config.py                      # transcription_pc_impact
app/ui/main_window.py                   # combo + hint
tests/test_pc_impact.py                 # NEW
../Transcriptor/transcribe.py           # honor --threads for torch
README.md / CLAUDE.md                   # document the control
```

## Phase 0 / Phase 1

See [research.md](./research.md), [data-model.md](./data-model.md), [contracts/ui-pc-impact.md](./contracts/ui-pc-impact.md), [quickstart.md](./quickstart.md).

## Complexity Tracking

None. No constitution violations.
