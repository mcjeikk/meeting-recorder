# Contract: Uso del PC (Recorder UI → job → CLI)

**Feature**: `011-transcription-pc-impact` | **Date**: 2026-09-08

## UI (section 4, after Velocidad / calidad)

- Label: `Uso del PC:`
- Combo items (stable order): `Usar más CPU (más rápido)` (`full`), `Dejar el PC usable` (`usable`)
- Hint updates with the selection; must state that quality and PC use are independent and that usable is slower
- Disabled + same tooltip as preset when Transcriptor is missing
- Persisted immediately on change (`AppConfig.save`)

## Enqueue

```
JobStore.enqueue(media, language, preset=..., pc_impact=...)
```

Worker and record-finished / import paths pass the live combo (or saved config). The job JSON MUST contain `pc_impact`.

## Launch

```
--threads <threads_for_impact(job.pc_impact)>
creationflags = CREATE_NO_WINDOW | priority_for(job.pc_impact)
env = subprocess_env(job.pc_impact)   # includes BLAS/torch thread caps
```

Transcriptor, when `--threads N` and N > 0, MUST also `torch.set_num_threads(N)` (best-effort) so diarization cannot ignore the cap.
