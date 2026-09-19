# Research: what the model load actually costs, and who pays it

**Date**: 2026-09-18 · **Machine**: laptop without a dedicated GPU · **Configuration**: `large-v3-turbo`, speakers on, "Usar más CPU" (`full`)

Both runs below came from the manual acceptance of specs 020 and 021: the real worker, the real engine, short samples cut with `-c copy` from real recordings, everything inside a throwaway sandbox.

## Run A — three samples of 45 s

| File | Engine run | Audio | Promised | Real | Error |
|---|---|---|---|---|---|
| Proy GÉNESIS - Alineación | first of its run | 45 s | 90 s | 55 s | +35 s |
| Proy GÉNESIS - Revisión mapa | first of a run of two | 45 s | 90 s | 54 s | +36 s |
| 1er reunion arq empresarial | second of that run | 45 s | 90 s | 42 s | +48 s |

The promise is the same 90 s for all three: `45 × 1.10 + 40`. The third file reused the models loaded by the second (they shared one command; the notice showed "archivo 1 de 2" and "archivo 2 de 2") and finished 12 s sooner.

**The load cost, measured twice**: 55 − 42 = 13 s and 54 − 42 = 12 s. Same audio length, same configuration, the only difference being who loads the models. The constant in use was 40 s, over three times the measurement.

## Run B — two samples of 300 s

| File | Engine run | Audio | Promised | Real | Error |
|---|---|---|---|---|---|
| Proy GÉNESIS - Revisión mapa | own run | 300 s | 370 s | 313 s | +57 s |
| 1er reunion arq empresarial | own run | 300 s | 370 s | 330 s | +40 s |

Here the second file was queued a moment after the engine had already started with the first, so each file got its own run and **both paid a load** — and both still finished 40–57 s early. This is the evidence that the constant itself is too large, independent of the once-per-run defect.

Whole run: 648 s of wall clock for 600 s of audio, **1.08×**, exactly the factor documented in `CLAUDE.md` for this configuration.

## What the numbers say

1. **Two separate defects, same direction.** The load is charged to every file (it belongs to the run), and the charge is more than three times what the load costs.
2. **Expected effect of the fix**, with the charge at 12 s: run B becomes `300 × 1.10 + 12 = 342 s` against 313 s and 330 s real (+9 % and +4 %, from +18 % and +12 %). Run A's third file becomes `45 × 1.10 = 50 s` against 42 s real, instead of 90 s.
3. **Why it matters most on queues of short files**: for a one-hour meeting, 40 s is 1 % of the estimate and disappears in the 5-minute rounding of "listo ~21:40". For ten imported clips of a few minutes, the batch estimate carried nine phantom loads — six minutes of invented waiting.

## Alternatives considered

- **Learn the load like the factor is learned.** Rejected for now: separating load from processing inside one measurement would need per-phase timings the engine's log does not provide. The factor already learns steady-state speed, which is the part that varies most between machines.
- **Spread the load across the files of the run.** Rejected: the user reads each file's promise separately, so an average is wrong for every file instead of right for the one that pays.
- **Drop the charge entirely.** Rejected: the first file of a run really does wait for the models, and dropping it would make the estimate optimistic — the one direction that does harm, because the user comes back to find it unfinished.
- **Measure the load with a dedicated cold run.** Not needed: run A already isolates it, because two files of identical length differed only in whether they loaded the models. A cold-cache machine would pay more, which is why the constant is documented with its method so it can be re-measured.

## Risk

The constant is measured on one machine with warm file caches. On a cold start, or on a machine with slower storage, the load costs more and the estimate will again be short for the first file of a run — which spec 021 already handles by stretching the estimate rather than promising the past. The learned factor absorbs the rest over time.
