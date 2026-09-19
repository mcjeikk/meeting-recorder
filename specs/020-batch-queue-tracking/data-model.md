# Data Model: Truthful tracking of a multi-file transcription batch

No new persisted field. The change is in **which states are legal at the same time** inside a batch, plus two derived values that travel only in the UI snapshot.

## Queue job (`TranscriptionJob`, persisted as one JSON per job)

Relevant existing fields: `id`, `media_path`, `status`, `pid`, `log_path`, `work_wav`, `result_dir`, `attempts` / `max_attempts`, `no_diarize`, `note`, `error`, `output_base`, `created_at`.

### State meaning (tightened by this feature)

| State | Meaning | Inside a batch |
|-------|---------|----------------|
| `pending` | Not started, or started and left without a result | Every member except the one the engine is on |
| `extracting` | Work audio being produced | Before the run starts |
| `running` | The engine is processing **this** file right now | Exactly one member at a time |
| `done` | `transcripcion.txt` exists | Set as soon as it appears; `pid` cleared |
| `error` | Retries exhausted, with a human-readable reason | Per file, from that file's own log section |
| `cancelled` | User cancelled | Terminal: never promoted back to `running` |

### Invariants

- **INV-1**: For a given `pid`, at most one job is `running`.
- **INV-2**: `status == done` ⇒ `result_dir` set, `pid` cleared, no work audio left.
- **INV-3**: A job in `done` / `error` / `cancelled` is never re-promoted to `running` by log parsing.
- **INV-4**: A member left without a transcript when the engine moves on returns to `pending` (retry), bounded by `max_attempts`.
- **INV-5**: `work/<job id>/` exists only while the job is `pending` / `extracting` / `running`.

## Batch run (derived, not persisted)

Identified by the shared child `pid`; ordered as handed to the engine (`compatible_batch` order = argv order = processing order).

| Derived value | Source | Used for |
|---------------|--------|----------|
| cohort | jobs sharing the run's `pid` | harvesting, promoting the next file, per-file settle |
| `batch_pos` / `batch_total` | index of the live job in the cohort, cohort size | banner text "archivo N de M" (0/0 = single file) |
| live id | the job currently `running` | queue rows ("En espera" for the rest), summary counts, banner target |

## Progress record (derived per poll, not persisted)

Parsed from the shared log tail: `stage` (text), `pct` (`0..100`, `-1` = indeterminate, `None` = unchanged), `cli_name` (the engine's current file), `note` (e.g. speakers degraded).

### Transitions

- `> Procesando: X.wav` → live job becomes the match for `X.wav`; `pct` resets to 0; previous live job is closed out (done if its transcript exists, otherwise back to `pending`).
- `transcribiendo... NN%` → `pct = NN` for the live job.
- `Identificando hablantes` → `pct = -1` (indeterminate), stage names the phase.
- transcript appears for any cohort member → that member becomes `done` immediately.
- engine exits → every cohort member is settled from its own log section.

## Log section (derived)

The slice of the shared log between a file's `> Procesando:` line and the next one. Empty slice = the file never started. Only this slice feeds: error text, out-of-memory detection, and "died during speaker identification".
