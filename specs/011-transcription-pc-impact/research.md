# Research: 011-transcription-pc-impact

**Date**: 2026-09-08

## Decision 1 — Quality and PC impact are orthogonal

- **Choice**: Keep Rápido / Equilibrado / Máxima. Add `transcription_pc_impact` = `usable` | `full`.
- **Why**: Equilibrado already uses `large-v3-turbo` + diarization. The freeze is not “wrong preset”; it is CPU saturation. The user wants Máxima *and* a usable desktop.
- **Alternatives rejected**: Folding “light PC” into Rápido (would drop speakers); forcing medium/small models (violates FR-009); a raw thread spinner (too low-level for one power user).

## Decision 2 — Why current BELOW_NORMAL + `--threads cpu-2` still freezes the PC

- **Finding**: Recorder already passes `--threads max(1, cpu-2)` and `BELOW_NORMAL_PRIORITY_CLASS`. faster-whisper honors `--threads`. **pyannote / PyTorch / OpenMP do not** — Transcriptor never sets `OMP_NUM_THREADS`, `MKL_NUM_THREADS`, or `torch.set_num_threads`. Diarization (the slow half of Equilibrado/Máxima) can pin every logical core. On Windows, BELOW_NORMAL still lets a full-core worker starve interactive apps.
- **Choice**: For `usable`, cap threads (Whisper **and** BLAS/torch env) and use `IDLE_PRIORITY_CLASS`. For `full`, keep cpu-2 + BELOW_NORMAL **and** still set the same env cap to that thread count so diarization cannot exceed `--threads`.
- **Alternatives rejected**: EcoQoS-only (Win11-specific, incomplete); job objects with hard CPU % (over-engineering, constitution V); fusing venvs.

## Decision 3 — Thread budget

| Logical CPUs | usable | full (legacy) |
|--------------|--------|----------------|
| 2 | 1 | 1 |
| 4 | 2 | 2 |
| 8 | 4 | 6 |
| 16 | 4 | 14 |

- **Choice**: `usable = max(1, min(4, n // 2))`, `full = max(1, n - 2)`. Cap of 4 for usable is the interactive sweet spot on this class of laptop; extra cores past 4 on CPU Whisper have diminishing returns and kill the desktop.
- **Why default full (2026-09-10)**: the user wants speed unless they explicitly pick usable. Mid-job switch cannot add threads; starting at full avoids that trap. Usable remains available.

## Decision 4 — Job snapshot and legacy

- New jobs / new config default `full`. Old factory-usable configs migrate once.
- Job JSON missing `pc_impact` → treat as `full` (do not retune an already-queued heavy job).
- Retry reuses stored field (same pattern as preset).

## Decision 5 — Transcriptor change (minimal)

- Recorder sets env on the child. Also call `torch.set_num_threads` in Transcriptor when `--threads > 0`, because some wheels ignore env after import.
- Do not change Transcriptor’s CLI contract beyond honoring the existing `--threads` for torch/OpenMP.

## Decision 6 — Out of scope

- GPU requirement, model-load daemon (005), changing Equilibrado’s model, numeric sliders.
