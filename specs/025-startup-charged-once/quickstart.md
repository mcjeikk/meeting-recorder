# Quickstart: checking the estimate against reality

## The cheap checks

```powershell
# Aritmética del cobro y las garantías de la 021 (rápido, sin motor):
.\.venv\Scripts\python.exe -m unittest tests.test_eta tests.test_batch_tracking

# Cableado completo contra el motor real, en sandbox desechable:
.\.venv\Scripts\python.exe verify_transcription.py --quick
```

## Re-measuring the model load

The number in `STARTUP_SECONDS` is a measurement, not a preference. To repeat it, transcribe **two samples of the same length** in a single batch, with the same language, preset, speakers and PC usage, so that they land in one engine run. The first file of the run pays the load, the second does not: the difference between their times **is** the load.

On 2026-09-18, with 45 s samples, `large-v3-turbo`, speakers on, "Usar más CPU": 55 s and 54 s for a file that loaded the models, 42 s for the one that reused them → 12–13 s.

Two things to watch or the measurement lies:

- **Do not measure with a recording in progress.** The worker suspends the engine, and the clock that matters is active time, not wall clock.
- **Samples must be long enough to be comparable** but short enough to repeat; 45 s worked. Anything under 60 s of audio is deliberately rejected as a speed sample, so these runs do not teach the learned factor anything.

## Reproducing the acceptance run

The acceptance used throwaway samples of the most recent recordings and drove the real worker, rendering the notice and the queue rows with the same functions the window uses (`queue_status.format_queue_line`, `batch_suffix`, `eta_suffix`, `batch_eta_text`). What it checks, per file:

1. Only one file is "En curso" at a time; the rest of the batch says "En espera".
2. The notice never names a file that is already finished.
3. Each file is marked ready at its own time, not all at the end.
4. The percentage keeps advancing while speakers are identified.
5. No label from an earlier phase appears next to a transcription percentage.
6. The promised time is never already in the past, and lands near the real one.

**Baseline before this feature** (2026-09-18): every criterion passed except the last. Two samples of 300 s were promised 370 s and took 313 s and 330 s (+18 % and +12 %); a 45 s sample was promised 90 s and took 42 s.

**Expected after it**: `300 × factor` for a file that reuses models, plus 12 s for the first file of the run.

## Where to look when the estimate is off

| Symptom | Likely cause |
|---|---|
| Promises far too much time on the first file only | the load charge is too high for this machine; re-measure as above |
| Promises too little and keeps stretching | the factor is low for this configuration; three real samples fix it |
| No time at all | the working WAV has no measurable duration — by design, no guessing |
| The batch total disappears | some pending file has no known duration (unchanged from spec 021) |
