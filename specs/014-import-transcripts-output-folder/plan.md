# Implementation Plan: Imported Transcripts Follow Carpeta de Salida

**Branch**: `014-import-transcripts-output-folder` | **Date**: 2026-09-09 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/014-import-transcripts-output-folder/spec.md`

## Summary

Imported transcriptions currently call `output_dir_for(media)` which is always `{media.parent}/Transcripciones`. That matched specs 009/010 (source-adjacent imports) but contradicts the user: Carpeta de salida must receive those transcripts too. Snapshot an absolute `output_base` on each job at enqueue (selected folder for imports, video parent for new meetings). Worker `--output` and `result_dir` use that snapshot. Empty/legacy jobs keep media-parent behavior. Original media is never copied. Work WAV/queue/logs stay in `%LOCALAPPDATA%`.

## Technical Context

**Language/Version**: Python 3.11.9 (Recorder `.venv`)

**Primary Dependencies**: Existing `JobStore` / worker / `output_dir_for`; PySide6 only for hint copy. Transcriptor CLI unchanged (`--output` must remain absolute).

**Storage**: Job JSON in `%LOCALAPPDATA%\MeetingRecorder\transcripts\queue\`; new optional field `output_base`. User-visible txt/srt/json under `{output_base}/Transcripciones/{stem}/`.

**Testing**: unittest (`tests/test_selected_folder_outputs.py` plus import enqueue). Headless UI not required if helpers are testable without Qt.

**Target Platform**: Windows desktop (Grabador)

**Project Type**: Desktop app (PySide6) + sibling CLI subprocess

**Performance Goals**: No extra copy of imported media; enqueue destination decision in well under 1 s

**Constraints**: Argument lists, never `shell=True`; absolute `--output`; Recording Always Wins; no fused venv; no LLM

**Scale/Scope**: One user; one Carpeta de salida; sequential queue

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- I. Recording Always Wins — PASS (destination is a path snapshot; does not start work while recording)
- II. Privacy Is Local — PASS (no cloud)
- III. Sibling subprocess — PASS (same `transcribe.py`; success = exit + artifacts)
- IV. Robust paths — PASS (absolute `--output`; work files stay off OneDrive)
- V. Simplicity — PASS (one extra job field; no second picker)

Post-design re-check: unchanged. Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/014-import-transcripts-output-folder/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/ui-import-output-folder.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
app/transcription/integration.py   # output_dir_for / result_dir_for accept output_base
app/transcription/jobs.py          # TranscriptionJob.output_base; enqueue kwarg
app/transcription/worker.py        # pass snapshot into CLI and settle
app/ui/main_window.py              # import enqueue + hint; meeting enqueue uses video parent
README.md                          # import results under Carpeta de salida

tests/test_selected_folder_outputs.py
tests/test_transcribe_any_file.py   # if any source-adjacent assertions remain
```

**Structure Decision**: Extend existing helpers; no new module.

## Complexity Tracking

> None
