# Implementation Plan: The queue forgets what it no longer needs

**Branch**: `023-queue-history-pruning` | **Date**: 2026-09-18 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/023-queue-history-pruning/spec.md`

## Summary

Finished job records get an end of life: 30 days, and at most the 200 newest. The decision is a pure function over records plus an injected clock (`app/transcription/retention.py`), so every limit and edge case is testable without touching the disk; `JobStore.prune_history()` applies it, deleting each pruned record's log and any log whose record is gone. Pruning runs on the worker thread inside `_reconcile()`, next to the orphan audio purge that already runs at startup, and says nothing.

Because a finished record is currently also how the app knows a file was already transcribed, the import path stops depending on it: when there is no record, `import_media.classify_import` asks the destination folder (`result_dir_for(...) / "transcripcion.txt"`) — the same fact the worker uses to decide success. The user-visible behavior of importing an already-transcribed file is unchanged; only its source of truth moves.

## Technical Context

**Language/Version**: Python 3.11.9 (Recorder `.venv`)

**Primary Dependencies**: standard library only (`datetime`, `pathlib`). No new dependency, no Qt in the pruning path.

**Storage**: `%LOCALAPPDATA%\MeetingRecorder\transcripts\queue\*.json` and `...\logs\*.log`. Nothing else is written or read.

**Testing**: unittest with synthetic records and an injected `now` (`tests/test_retention.py`): both limits, the protected statuses, orphan logs, corrupt timestamps, idempotence; plus an import-path test that a pruned-but-transcribed file is still recognised (`tests/test_import_media.py`).

**Target Platform**: Windows desktop (Grabador)

**Project Type**: Desktop app (PySide6) + sibling CLI subprocess

**Performance Goals**: a pass over 300 records well under a second; no perceptible change at startup.

**Constraints**: never raise (a cleanup that throws stops running); never delete anything outside `queue/` and `logs/`; never remove a record with live or failed status; must work with records written by older versions (missing or differently-built fields).

**Scale/Scope**: one user, tens of meetings per month.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- I. Recording Always Wins — PASS (pruning is a bounded pass over small JSON files at startup; it never competes with a recording and never touches a live record)
- II. Privacy Is Local — PASS (it only deletes local bookkeeping; transcripts and recordings are out of scope by requirement)
- III. Transcription stays a sibling subprocess — PASS (the engine is not involved; the "already transcribed" answer uses the artifact the engine already writes)
- IV. Robust paths and processes — PASS (no subprocess; path handling via `pathlib` with OneDrive-safe absolute paths; every deletion is failure-tolerant)
- V. Simplicity — PASS (one pure module, one store method, one call site; no cache, no index, no database)
- Verification & Quality — PASS (pure functions with an injected clock make every limit and edge case testable; `verify_transcription.py --quick` still passes end to end)

Post-design re-check: unchanged. Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/023-queue-history-pruning/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/queue-retention.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
app/transcription/retention.py       # NEW: limits + the pure decision (which records and logs go)
app/transcription/jobs.py            # JobStore.prune_history(): apply the decision, tolerate failures
app/transcription/integration.py     # transcript_exists(media, output_base): the disk-based answer
app/transcription/import_media.py    # classify_import falls back to disk when there is no record
app/transcription/worker.py          # _reconcile: prune after the orphan work purge
CLAUDE.md                            # what the queue keeps and for how long
README.md                            # one line in the transcription section

tests/test_retention.py              # NEW: both limits, protected statuses, orphan logs, corrupt data, idempotence
tests/test_transcribe_any_file.py    # pruned record + transcript on disk is still "already transcribed"
```

**Structure Decision**: keep the decision (pure, testable) separate from its application (filesystem, failure-tolerant). `retention.py` holds the numbers and the rule; `JobStore` keeps all filesystem knowledge, as it does for the work purge.

## Complexity Tracking

> No constitution violations; section intentionally empty.
