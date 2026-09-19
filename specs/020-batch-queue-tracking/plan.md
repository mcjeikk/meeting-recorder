# Implementation Plan: Truthful tracking of a multi-file transcription batch

**Branch**: `020-batch-queue-tracking` | **Date**: 2026-09-18 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/020-batch-queue-tracking/spec.md`

## Summary

Compatible pending jobs share one `transcribe.py` run (spec 015: one model load for N files). The worker marked **every** member `running` with the same pid and log, then monitored only the first one: the list showed 10 "En curso", the banner froze on the batch leader and its ASR percentage, and nothing was resolved until the whole 22.5 h run exited. Fix the tracking at the source: parse `> Procesando: <wav>` to know which file the CLI is really on, keep exactly one job `running` (the rest stay `pending`), harvest `done` the moment `transcripcion.txt` appears, and reset/blank the percentage on file switch and during diarization. Resolution (`_settle`) reads only the **section** of the shared log that belongs to each file, so one file's error/OOM never degrades the others. Housekeeping: reclaim orphan work WAVs at reconcile. No change to the Transcriptor, the CLI contract, or the batching decision.

## Technical Context

**Language/Version**: Python 3.11.9 (Recorder `.venv`)

**Primary Dependencies**: Existing `JobStore` / `TranscriptionWorker` / `queue_status`; new pure-Python module `app/transcription/cli_progress.py`; PySide6 only for the banner/list. Transcriptor CLI unchanged (it already prints `> Procesando:` and `transcribiendo... NN%` under `TRANSCRIPTOR_PLAIN=1`).

**Storage**: Job JSON in `%LOCALAPPDATA%\MeetingRecorder\transcripts\queue\` (no new persisted field; `batch_pos`/`batch_total` travel only in the UI snapshot). Shared log per batch in `...\transcripts\logs\`. Work WAVs in `...\transcripts\work\<job id>\`.

**Testing**: unittest. `tests/test_batch_tracking.py` drives the real `_monitor` loop with a fake process that writes the log step by step; `tests/test_cli_progress.py` covers parsing; `tests/test_queue_status.py` covers the rendered rows and the batch suffix.

**Target Platform**: Windows desktop (Grabador)

**Project Type**: Desktop app (PySide6) + sibling CLI subprocess

**Performance Goals**: Status refresh within one poll (~1 s) of a transcript appearing; polling cost stays O(batch size) file stats per second, not O(queue history).

**Constraints**: Argument lists, never `shell=True`; success decided by artifacts (batch exit code is global); Recording Always Wins (suspend keeps working); worker callbacks run off the Qt thread, so all UI updates go through the existing signal.

**Scale/Scope**: One user; one queue drained sequentially; batches observed up to 10 files / 22.5 h.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- I. Recording Always Wins — PASS (pause/suspend path untouched; the paused stage keeps naming the live file, and no new work is started while recording)
- II. Privacy Is Local — PASS (only reads a local log and local artifacts; no cloud, no LLM)
- III. Sibling subprocess — PASS (no change to the CLI or its venv; success still = `transcripcion.txt`; the log stays cosmetic for progress, and is now *also* used for per-file attribution of failures, which never overrides artifact-based success)
- IV. Robust paths — PASS (argument lists unchanged; queue/logs/work stay in `%LOCALAPPDATA%`; matching is done on file names, tolerant of accents/brackets/spaces)
- V. Simplicity — PASS (one small parsing module + status bookkeeping; no new process, no scheduler, no extra persisted state)

Post-design re-check: unchanged. Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/020-batch-queue-tracking/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/cli-progress-log.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
app/transcription/cli_progress.py   # NEW: parse the plain log; match a job to the CLI's current file; per-file log sections
app/transcription/worker.py         # one live job per batch; harvest done on artifact; per-file settle; batch position in the snapshot; work GC at reconcile
app/transcription/jobs.py           # queue_counts(live_id); purge_orphan_work_dirs()
app/transcription/queue_status.py   # non-live batch members render as "En espera"; batch_suffix() for the banner
app/ui/main_window.py               # banner follows the live file (+ "archivo N de M"); selection no longer hijacks it; per-file tray notice; stale import hint hidden
CLAUDE.md                           # invariants: one live job per batch, log read by sections, work GC

tests/test_batch_tracking.py        # NEW: monitor loop over a batch log + per-file attribution + work GC
tests/test_cli_progress.py          # NEW: parsing (file switch resets %, diarization blanks it, name matching)
tests/test_queue_status.py          # all-running batch renders one "En curso"; batch_suffix
```

**Structure Decision**: Keep the existing module split — parsing is a new dependency-free module so it is unit-testable without a process or Qt; state transitions stay in the worker; rendering stays in `queue_status` + the window. No new packages.

## Complexity Tracking

> No constitution violations; section intentionally empty.
