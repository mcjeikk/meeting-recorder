# Data Model: composing the estimate

Nothing new is persisted. This feature changes how an existing number is composed and who supplies one boolean.

## Engine run

One invocation of the transcription command, carrying one or more compatible files.

| Attribute | Meaning | Source |
|---|---|---|
| files | the files in the command, in order | the worker's cohort (`_cohort`) |
| load paid | whether the models are already in memory | position: the first file to be processed pays it |

Not stored: the worker knows it while the process lives, which is exactly as long as the estimate matters.

## Model-load charge

| Attribute | Value | Notes |
|---|---|---|
| cost | 12 s | measured 2026-09-18 on this machine (see research.md) |
| charged to | the first file of an engine run | every other file of the run reuses the models |
| scope | advisory only | no queue, retry or process decision reads it |

## Estimate of one file

```text
estimate = audio duration × factor(configuration)  +  (model-load charge if this file pays it)
```

- `factor(configuration)` is unchanged: the median of this machine's history for `model | speakers | PC usage` once there are three samples, the measured default before that.
- An unknown audio duration still yields no estimate at all, as in spec 021.
- The stretch rule, the 99 % ceiling and the floor from the engine's own percentage are untouched.

## Estimate of a batch

```text
batch estimate = remaining time of the live file
               + Σ (audio duration × factor) for each pending file of the run
```

The pending files add work only: their models are already loaded by the time they start. If any pending file has no known duration, no batch estimate is shown — unchanged from spec 021.

## Speed sample

Unchanged in format and meaning: `(audio duration, active seconds)` per configuration.

| Concern | Decision |
|---|---|
| A first-file sample includes the load | accepted: ~12 s over runs of minutes, absorbed by the median of three or more samples |
| Very short files would be dominated by it | already rejected by the existing minimum of 60 s of audio per sample |
