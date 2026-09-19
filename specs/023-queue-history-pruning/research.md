# Research: The queue forgets what it no longer needs

## R1. What the queue actually costs today

**Measured on 2026-09-18** (`%LOCALAPPDATA%\MeetingRecorder\transcripts`):

```text
queue json: 64      (64.5 KB)   oldest 2026-06-10, newest 2026-09-18
logs:       68      (0.08 MB)
work items: 0                   (the orphan purge from spec 020 is doing its job)
```

**Finding**: this is not a disk problem. It is a *read amplification* problem: `JobStore.all()` globs the folder, reads and JSON-parses every record, and rebuilds every dataclass — and it is the substrate of `pending()`, `active()`, `queue_counts()`, `find_by_media()`, `count_clearable()`, `purge_orphan_work_dirs()` and the worker's cohort grouping. While a job runs, the monitor loop asks these questions every second or two, and the UI asks again on every refresh. 64 records is already 64 file reads per question; nothing bounds it.

**Decision**: bound the history rather than optimise the reads (caching a mutable, multi-process-visible queue is how stale-state bugs are born — spec 020 was exactly that class of bug).

## R2. Why finished records cannot simply be deleted at completion

`JobStore.enqueue` returns `None` when a record for the same media exists in an active state **or** `done`, and `import_media.classify_import` turns that into "Ya hay una transcripción de X". So a finished record is doing double duty: history (nobody reads it) and *idempotence* (everybody depends on it).

**Decision**: move the idempotence answer to where the truth already lives — the destination folder. `result_dir_for(media, output_base)` already resolves `<destino>\Transcripciones\<stem>\`; the presence of `transcripcion.txt` there is the same fact the worker itself uses to decide success (spec 020: "success is decided by the transcript existing").

**Alternatives considered**:

| Option | Why rejected |
|--------|----------------|
| Keep a separate "already transcribed" index file | A second source of truth to keep in sync; the folder is already authoritative |
| Never prune finished records | The growth is unbounded and on every hot path |
| Prune but accept re-transcription | Hours of CPU silently repeated — the opposite of Principle I |
| Ask the user each time | The user explicitly chose the silent, disk-based answer |

## R3. Which timestamp decides age

Records carry `created_at`, `started_at`, `finished_at` (ISO strings from `datetime.now().isoformat(timespec="milliseconds")`, local time, no timezone).

**Decision**: age by `finished_at`, falling back to `created_at`, falling back to "infinitely old". Compare with `datetime.fromisoformat`, and on any parse failure treat the record as old **but** still subject to the count cap ordering (so a corrupt timestamp cannot make a record immortal, and cannot crash the pass either).

**Rationale**: `finished_at` is when the record became history. Naive local timestamps are fine because both sides of the comparison come from the same machine.

## R4. Two limits, one rule

The user asked for both an age window and a count cap.

**Decision**: a finished record survives when it is newer than 30 days **and** among the 200 newest finished records. Equivalently, prune when it is older than the window **or** beyond the cap. Ordering for the cap uses the same timestamp as the age test, so both bounds agree on what "newest" means.

**Rationale**: the age window is what the user thinks in ("last month"); the cap is the guard against a pathological month (a 500-file import binge) that the window alone would not catch.

## R5. What must never be pruned

| Status | Pruned? | Why |
|--------|---------|-----|
| `pending`, `extracting`, `running` | Never | Live work; deleting a record mid-flight would orphan a child process |
| `error`, `cancelled` | Never | Visible in the list; the log is the only explanation. The existing "clear failed" action is the user's decision |
| `done` | Yes, per R4 | History; already hidden from the list by spec 020 |

**Decision**: automatic pruning touches only `done`. This keeps pruning invisible: the queue list shows exactly the same rows before and after.

## R6. Logs

Logs are named `<stem>_<job id>.log`. A log is prunable when its record is pruned, or when no record exists for it at all (earlier manual cleanups left 68 logs for 64 records).

**Decision**: derive the set of live log paths from the surviving records and delete the rest, matching by the record's own `log_path` and, as a fallback, by the `_<job id>.log` suffix (older records built the path differently). Deletion failures are swallowed: the next start retries.

**Rationale**: the same reasoning as the orphan work purge — a cleanup that can throw is a cleanup that stops running.

## R7. Where pruning runs

`TranscriptionWorker._reconcile()` already runs once at startup, adopts or settles interrupted jobs, and ends by calling `purge_orphan_work_dirs()`.

**Decision**: prune there, right after the work purge, on the worker thread. Startup cost is one pass over records already being read by the reconcile itself.

**Rationale**: it is the existing housekeeping seam, it is off the Qt thread, and it cannot run while another instance owns the queue (the worker lock gates `_reconcile`).

## R8. Out of scope

- Optimising `JobStore.all()` (caching, an index, SQLite): bounded history removes the pressure; revisit only if a real measurement demands it.
- Pruning the transcripts themselves or the recordings: never, by requirement.
- A UI control for pruning: the user chose silent-at-startup only.
