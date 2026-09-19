# Data Model: The queue forgets what it no longer needs

No new persisted structure. This feature *removes* instances of an existing one and changes where one answer comes from.

## Retention limits

| Field | Value | Rules |
|-------|-------|-------|
| `HISTORY_DAYS` | 30 | Finished records older than this are pruned |
| `MAX_HISTORY` | 200 | At most this many finished records are kept, newest first |
| `MAX_DELETIONS_PER_PASS` | 100 | Deletions one pass may perform, oldest first; the rest waits for the next start |
| applied together | — | A record survives when it is inside the window **and** inside the cap |

Both live in `app/transcription/retention.py` and nowhere else (FR-010).

## Finished record (existing `TranscriptionJob`, status `done`)

| Field used | Meaning | Rules |
|------------|---------|-------|
| `status` | job state | Only `done` is prunable; every other status is protected |
| `finished_at` | when it became history | Primary age key; ISO local string |
| `created_at` | fallback age key | Used when `finished_at` is empty |
| `log_path` | its engine log | Deleted with the record |
| `id` | job id | Fallback match for a log named `*_<id>.log` |

### Invariants

- **INV-1**: A record with status `pending`, `extracting`, `running`, `error` or `cancelled` is never pruned, at any age.
- **INV-2**: A record whose timestamps cannot be parsed is treated as old (prunable), never as immortal, and never raises.
- **INV-3**: Pruning is idempotent once converged: a second pass on a queue already inside the limits removes nothing.
- **INV-11**: One pass deletes at most `MAX_DELETIONS_PER_PASS` records (oldest first) and at most as many logs; a backlog converges over successive starts.
- **INV-4**: Pruning writes nothing; it only deletes inside `queue/` and `logs/`.
- **INV-5**: The newest 200 finished records inside the window are always kept, so the most recent history stays inspectable.

## Log file

| Field | Meaning | Rules |
|-------|---------|-------|
| path | `logs\<stem>_<job id>.log` | Kept while its record exists |
| orphan | no record refers to it | Pruned (earlier manual cleanups left 68 logs for 64 records) |

### Invariants

- **INV-6**: After a pass, every remaining log belongs to a surviving record.
- **INV-7**: A log that cannot be deleted (locked, antivirus) does not abort the pass; the next start retries.

## "Already transcribed" answer

| Source | Before | After |
|--------|--------|-------|
| a `done` record for the media path | authoritative | still used first (it also carries the result folder) |
| `<destino>\Transcripciones\<stem>\transcripcion.txt` | not consulted | consulted when no record exists |

### Invariants

- **INV-8**: A file whose transcript exists on disk is never queued again by the import path, with or without a record.
- **INV-9**: A file whose transcript was deleted is queued normally, with or without a record.
- **INV-10**: An unreachable destination is treated as "not transcribed" (the file gets queued): the safe failure is redundant work, never a lost transcription.

## Pruning result (in-memory only)

| Field | Meaning |
|-------|---------|
| records | how many finished records were removed |
| logs | how many log files were removed |

Returned for tests and logging; never shown to the user (FR-005).
