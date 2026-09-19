# Contract: progress and finish-time estimate

The estimate is computed by `app/transcription/eta.py` from observations the worker already has. This file pins the interface so the UI and the worker cannot drift, and so the estimate can never affect real behavior.

## Inputs (per poll, per file in progress)

| Input | Source | Unknown value |
|-------|--------|---------------|
| `audio_seconds` | work WAV size (16 kHz mono PCM) | `0.0` |
| `factor` | speed store for `model \| speakers \| pc usage` | documented default |
| `active_elapsed` | wall time while the child ran and was not suspended | `0.0` |
| `asr_pct` | engine's transcription percentage (`-1`/`None` = none) | `None` |
| `done` | the file's transcript exists | `False` |
| `now` | injected clock (tests pass a fixed value) | — |

## Outputs

| Output | Type | Guarantee |
|--------|------|-----------|
| `progress` | `int \| None` | `None` when `audio_seconds` is unknown; otherwise 0..99 while working, 100 only when `done` |
| `eta_epoch` | `float` | `0.0` when unknown; otherwise strictly greater than `now` |
| `total_seconds` | `float` | The (possibly revised) estimate used, for the caller to sum a run total |

## Rules

- **E-1**: Advisory only. No scheduling, retry, cancellation or process decision may read these outputs (constitution I and III).
- **E-2**: `progress` is monotonic within an attempt: callers pass the previous value and the model never returns less.
- **E-3**: `progress` is floored by the engine's transcription percentage scaled into the transcription phase, so a faster-than-estimated machine is not under-reported.
- **E-4**: `progress` is capped at 99 until the transcript exists; reaching 100 is an artifact fact, never a time fact.
- **E-5**: When `active_elapsed ≥ 0.95 × total`, `total` is extended to `active_elapsed / 0.95` so the finish time moves forward instead of into the past.
- **E-6**: Suspended work does not advance `active_elapsed`; the caller freezes the displayed finish time and labels it paused.
- **E-7**: Unknown `audio_seconds` yields no percentage and no finish time — never a guessed one.
- **E-8**: Finish times are rendered rounded up to whole 5-minute marks, with an explicit day when the finish is not today.

## Learning store

- **L-1**: A sample is recorded only when a file completes successfully, as `[audio_seconds, active_seconds]` under its configuration key.
- **L-2**: Files shorter than 60 s are not recorded (startup dominates and would poison the factor).
- **L-3**: A key uses its own median once it has ≥3 samples; before that, the documented default.
- **L-4**: At most 20 samples per key are kept (oldest dropped), so a change in machine conditions is reflected within a few files.
- **L-5**: A missing, empty or corrupt store behaves exactly like "no history" and must never raise.
