# Data Model: Progress that means something, and a time estimate

## Speed sample store (new, persisted)

File: `%LOCALAPPDATA%\MeetingRecorder\transcripts\speed.json` — local only, outside OneDrive, beside the queue and logs.

```json
{
  "version": 1,
  "samples": {
    "large-v3-turbo|speakers|full": [[3600.0, 3890], [2172.8, 2409]],
    "large-v3-turbo|speakers|usable": [[5400.0, 7830]]
  }
}
```

| Field | Meaning | Rules |
|-------|---------|-------|
| key | `model \| speakers\|nospeakers \| pc usage` | Derived from the job at completion time (its degraded `no_diarize` counts as `nospeakers`) |
| sample | `[audio_seconds, active_seconds]` | Appended when a file completes; only positive pairs; audio ≥ 60 s (short files are dominated by startup) |
| history length | last 20 per key | Oldest dropped first |
| unreadable / corrupt file | treated as empty | Defaults are used; the file is rewritten on the next completion |

**Factor for a key**: median of `active / audio` over that key's samples when it has ≥3, otherwise the documented default for that key (see research R6). Unknown key → default for the same model with speakers on.

## Estimate (derived per poll, not persisted)

| Value | Source | Notes |
|-------|--------|-------|
| `audio_seconds` | work WAV size: `(size − 44) / 32000` | 0 / unknown when the WAV is missing or not yet extracted |
| `factor` | speed store for the job's key | Includes the startup allowance separately |
| `estimated_total` | `audio_seconds × factor + startup allowance` | Revised upward when `active_elapsed ≥ 0.95 × estimated_total` and the file is not done |
| `active_elapsed` | accumulated wall time while the child ran and was not suspended | Resets per attempt, not per file switch inside an attempt |
| `progress` | `max(active_elapsed / estimated_total, transcription_pct_floor)`, capped at 99 | 100 only when the transcript exists; `None` when `audio_seconds` is unknown |
| `eta_epoch` | `now + (estimated_total − active_elapsed)` | 0 when unknown or paused-with-no-estimate |
| run total | current file remainder + `audio × factor` of the run's members not yet finished | Shown in the queue summary |

### Invariants

- **INV-1**: `progress` never decreases within an attempt.
- **INV-2**: `eta_epoch` is never in the past; if the moment passes, the estimate is extended instead.
- **INV-3**: While suspended, `active_elapsed` does not grow and the displayed finish time is frozen and labelled paused.
- **INV-4**: Unknown `audio_seconds` ⇒ no percentage and no finish time (stage text only).
- **INV-5**: A file whose transcript exists reports 100 and no finish time.
- **INV-6**: Estimates never feed scheduling, retries or cancellation decisions.

## Snapshot additions (worker → UI, not persisted)

| Key | Type | Meaning |
|-----|------|---------|
| `progress` | int / None | Now the weighted percentage (was the raw transcription percentage) |
| `eta_epoch` | float | Expected finish of the file in progress; 0 = unknown |
| `eta_paused` | bool | The estimate is frozen because work is suspended |
| `batch_eta_epoch` | float | Expected finish of the whole run; 0 = unknown or single file |
| `batch_pos` / `batch_total` | int | Unchanged from spec 020 |

## Display formatting

| Situation | Text |
|-----------|------|
| Finishes today | `listo ~21:40` |
| Finishes tomorrow | `listo mañana ~03:20` |
| Later than tomorrow | `listo el vie ~09:15` |
| Paused | `estimación en pausa` |
| Unknown | (omitted) |

Rounding: up to the next whole 5 minutes, so the shown time never precedes the real estimate.
