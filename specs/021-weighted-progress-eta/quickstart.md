# Quickstart: validate progress and finish-time estimates

Prerequisites: Recorder `.venv` (Python 3.11.9). The automated checks need no engine run: the model takes an injected clock, and the monitor-loop test drives a fake process.

## 1. Automated checks (seconds)

```powershell
$env:QT_QPA_PLATFORM='offscreen'; $env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python.exe -m unittest tests.test_eta tests.test_batch_tracking -v
```

Expected coverage:

- weighted progress advances during speaker identification and never goes backwards (SC-002, SC-003);
- the estimate is extended instead of showing a past time (FR-007, E-5);
- suspended work freezes the estimate (FR-005, E-6);
- unknown audio duration shows no percentage and no time (SC-004, E-7);
- a file without speaker identification finishes at 100% without waiting for a phase that will not run (US2 scenario 2);
- finish times round up to 5-minute marks and name the day when it is not today (SC-008);
- the factor switches from the default to this machine's median at the third sample and survives a reload (SC-007).

Full suite must stay green:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

## 2. Check the model against your own history (no run needed)

```powershell
.\.venv\Scripts\python.exe -c @"
from app.transcription.eta import SpeedStore, estimate_total_seconds
s = SpeedStore()
for key in s.keys() or ['large-v3-turbo|speakers|full']:
    f = s.factor_for(key)
    print(f'{key:<40} factor {f:.2f}x  ->  1 h de audio = {estimate_total_seconds(3600, f)/60:.0f} min')
"@
```

Sanity bar from the audit (22 meetings): a 1 h meeting should read about 65–70 min with more CPU, about 90 min keeping the PC usable. Anything near 2 h means the stale factor is still in play.

## 3. Real run (manual acceptance)

1. Queue a meeting of known length and read the notice: it must show a weighted percentage and `— listo ~HH:MM`.
2. While it is in speaker identification, watch for at least two minutes: the percentage must keep moving (it used to sit at 90%).
3. Note the shown finish time and compare it with the real end: within ±25% of the total for files over 10 minutes (SC-001).
4. Start a recording mid-job: the notice must say the estimate is paused and the finish time must not move while suspended; after stopping, it resumes.
5. With a batch, the summary line must show the run total, e.g. `Resumen: 1 en curso · 6 en espera · lote listo ~03:20 (mañana)`.
6. After three files of the same configuration, `%LOCALAPPDATA%\MeetingRecorder\transcripts\speed.json` must contain samples and the factor used must be the machine's own median.
