# Contract: queue retention

Internal contract between `app/transcription/retention.py` (the decision), `JobStore` (the application) and the import path (the consumer of the consequence).

## The decision

```python
prunable_job_ids(jobs, *, now, days=HISTORY_DAYS, max_history=MAX_HISTORY) -> set[str]
oldest_first(jobs, ids, *, budget=MAX_DELETIONS_PER_PASS) -> list[str]
prunable_log_paths(log_dir, surviving_jobs) -> list[Path]
```

- **R-1**: Only records with status `done` may appear in the result.
- **R-2**: A `done` record is prunable when its age exceeds `days` **or** when it is not among the `max_history` newest `done` records.
- **R-3**: Age uses `finished_at`, else `created_at`, else "older than anything".
- **R-4**: An unparseable timestamp sorts as oldest; it never raises and never survives by accident.
- **R-5**: The functions are pure: no filesystem access, no clock of their own (`now` is injected).
- **R-6**: `prunable_log_paths` returns every `*.log` in the folder that no surviving record claims, matched by `log_path` and, as a fallback, by the `_<id>.log` suffix.
- **R-7**: `oldest_first` orders the prunable ids oldest first and truncates them to the pass budget, so a backlog is paid off from the far end and never all at once.

## The application

```python
JobStore.prune_history(*, now=None) -> dict   # {"records": int, "logs": int}
```

- **A-1**: Deletes the record files chosen by the decision, then the logs no surviving record claims.
- **A-2**: Never raises: every unlink is guarded, a failure is skipped and retried on the next pass.
- **A-3**: Never writes: no record is modified, no file is created.
- **A-4**: Touches nothing outside `queue/` and `logs/`.
- **A-5**: Returns the counts; the caller does not surface them to the user.
- **A-6**: Idempotent once converged: on a queue already inside the limits it removes nothing.
- **A-7**: Honours the pass budget for both records and logs (`oldest_first`, and the log list truncated the same way).

## The call site

- **C-1**: `TranscriptionWorker._reconcile()` calls it once at startup, after `purge_orphan_work_dirs()`, on the worker thread.
- **C-2**: It runs only when this instance owns the queue lock (`_reconcile` is already gated by it).
- **C-3**: No emission, no notification, no dialog.

## The consequence

```python
integration.transcript_exists(media_path, output_base=None) -> bool
import_media.classify_import(store, path, *, tool_available, output_base="") -> ImportResult
```

- **T-1**: `transcript_exists` is true when `<destino>\Transcripciones\<stem>\transcripcion.txt` exists.
- **T-2**: `classify_import` still prefers an existing record (it carries the result folder and the job snapshot).
- **T-3**: With no record and a transcript on disk, the result is `ALREADY_DONE` with the resolved result folder and today's message (`Ya hay una transcripción de <archivo>`), and the file is not queued.
- **T-4**: With no record and no transcript, the result is `OK` and the file is queued.
- **T-5**: Any error while checking the destination is treated as "no transcript" (the file gets queued).
- **T-6**: The summary line (`summarize_import_results`) keeps its current wording for both cases.
