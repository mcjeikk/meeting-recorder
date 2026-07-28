# Data Model: Transcription Queue Controls

## TranscriptionJob (extended)

Existing durable JSON job under `%LOCALAPPDATA%\MeetingRecorder\transcripts\queue\{id}.json`.

| Field | Change |
|-------|--------|
| `status` | Adds `cancelled` alongside `pending`, `extracting`, `running`, `done`, `error` |
| `language` | Unchanged semantics; now always set from UI-normalized value at enqueue |
| `error` | On cancel, MAY store short note e.g. `Cancelado por el usuario` |
| `finished_at` | Set when transitioning to `cancelled` |
| `pid` | Cleared after cancel settles |

### Status transitions (new)

```text
pending | extracting | running  --cancel-->  cancelled
error | cancelled  --clear_failed-->  (deleted from store)
error --retry--> pending   (unchanged)
```

Active set for “busy” UI: `{pending, extracting, running}` (unchanged).  
Clear-failed targets: `{error, cancelled}`.

## User Configuration

| Field | Values | Notes |
|-------|--------|-------|
| `transcription_language` | `es` \| `en` \| `auto` | Default `es`; unknown → `es` |

## UI state (ephemeral)

- Banner shows last emitted job snapshot (`_tx_last`).
- Cancel visible iff status ∈ active set.
- Clear failed enabled iff store has ≥1 error/cancelled (or last snap is error/cancelled — implementation may check store).
