# Contract: Job Cancel & Clear

## JobStore

```text
cancel(job_id) -> Optional[TranscriptionJob]
  - Load job; if missing or status not in {pending, extracting, running} → None
  - status = cancelled; error = "Cancelado por el usuario"; finished_at = now; pid = None
  - save; return job

clear_failed() -> int
  - Delete queue JSON for status in {error, cancelled}
  - Return count deleted

normalize_language(value) -> str
  - Allowed: es, en, auto (casefold)
  - Else → es
```

## TranscriptionWorker

```text
cancel(job_id) -> bool
  - store.cancel(job_id); if None → False
  - If this worker owns a live process for that job: terminate (then kill after short wait)
  - Set internal cancel flag / wake loop so monitor exits cleanly
  - Emit snapshot stage "Cancelada"
  - Return True

clear_failed() -> int
  - n = store.clear_failed()
  - Optionally emit UI refresh if last job was cleared
  - Return n
```

## Settle interaction

When `_settle` runs after process death, if job was already `cancelled`, do **not** auto-retry or mark `error`; keep `cancelled` and cleanup work wav.
