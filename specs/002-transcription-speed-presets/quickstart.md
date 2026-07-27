# Quickstart: Transcription Speed Presets

**Feature**: `002-transcription-speed-presets` | **Date**: 2026-07-27

## Prerequisites

- Recorder `.venv` (Python 3.11) and sibling Transcriptor available (`transcribe.py` + its `.venv`).
- Optional: short sample MP4 already recorded for enqueue tests.

## Automated / headless checks

```powershell
cd "C:\Users\jeissonsegura\OneDrive - Periferia IT Corp SAS\Documentos\Proyectos\Apps\Recorder"

# Unit: preset → CLI args (once tests exist)
.\.venv\Scripts\python.exe -m pytest tests/test_transcription_presets.py -q

# Headless UI: MainWindow constructs; preset control present (no show())
$env:QT_QPA_PLATFORM = "offscreen"
$env:PYTHONIOENCODING = "utf-8"
.\.venv\Scripts\python.exe smoke_test.py
```

## Manual Phase 1 validation

1. Launch Recorder; open transcription section.
2. Confirm three presets; switch each and read hint text.
3. Restart app → last preset restored.
4. Select **Rápido**, enable “Transcribir al terminar”, record ~30–60 s (or enqueue existing file).
5. Inspect queue JSON under `%LOCALAPPDATA%\MeetingRecorder\transcripts\queue\` → `preset`/`model`/`beam_size`/`no_diarize` match Rápido.
6. Inspect job log → argv contains `--model large-v3-turbo --beam-size 1 --no-diarize`.
7. Result: transcript without speaker labels is OK for Rápido.
8. Repeat once with **Equilibrado** and **Máxima calidad**; confirm CLI models both use recognition appropriately (`large-v3-turbo` beam 5 vs `large-v3` beam 5), no `--no-diarize` unless degraded retry.
9. While a job is queued, change UI preset → queued job JSON unchanged.
10. Start recording while a job runs → transcription yields (suspend) as today.

## Ordering check (SC-002)

Same machine, same ~1–3 min sample, successful runs:

`duration(Rápido) < duration(Equilibrado) ≤ duration(Máxima calidad)`

Record wall-clock from job start to done in logs or UI banner.

## Phase 2 (when implemented)

Document cold vs warm second job for same preset; confirm Transcriptor still separate process/venv and Recording Always Wins still holds.
