# Quickstart: The queue forgets what it no longer needs

## 1. What happens, and when

Every time the app starts, the worker's reconcile pass ends with two cleanups: the orphan audio purge (spec 020) and now the history prune. It says nothing.

| Kept | Forgotten |
|------|-----------|
| Finished jobs from the last 30 days, up to the newest 200 | Finished jobs older than that, or beyond the cap |
| Their logs | The logs of pruned jobs, and logs with no job at all |
| Queued, extracting, running, failed and cancelled jobs — at any age | (never pruned automatically; "Limpiar fallidas" is still yours) |
| Transcripts, recordings, settings, learned speed history | (out of scope by requirement) |

One pass deletes at most 100 records; a large backlog is paid off over successive starts.

## 2. Inspect the real queue

```powershell
$base = "$env:LOCALAPPDATA\MeetingRecorder\transcripts"
(Get-ChildItem "$base\queue" -Filter *.json | Measure-Object).Count
(Get-ChildItem "$base\logs" | Measure-Object).Count
```

Measured on this machine when the feature landed (2026-09-18):

```text
antes:   64 registros, 68 logs
borrado: 33 registros, 47 logs en 20 ms
despues: 31 registros, 21 logs
segunda pasada: {'records': 0, 'logs': 0} en 3 ms
pending() ahora: 2.0 ms por consulta   (era ~4 ms con 64 registros)
```

The 33 pruned records were finished jobs from 2026-06-10 to 2026-08-14. A backup of the pre-prune queue was kept at `%LOCALAPPDATA%\MeetingRecorder\transcripts_backup_2026-09-18` — delete it once you are comfortable.

## 3. The cost this bounds

`JobStore.all()` reads and parses every record, and it is the substrate of "what is pending", "what is running", "was this file transcribed", "how many in the batch" and every list refresh. Measured cost per question:

| Records | `all()` (cold) | `pending()` (warm) | `find_by_media()` |
|---------|---------------|--------------------|-------------------|
| 10 | 7.0 ms | 0.7 ms | 1.9 ms |
| 64 | 42.5 ms | 4.1 ms | 11.1 ms |
| 200 | 128 ms | 12.1 ms | 31.0 ms |
| 600 | 388 ms | 37.2 ms | 93.3 ms |

The cap at 200 is what keeps the right-hand column off the screen.

## 4. Checks after touching this area

```powershell
$env:PYTHONIOENCODING="utf-8"; $env:QT_QPA_PLATFORM="offscreen"
.\.venv\Scripts\python.exe -m unittest tests.test_retention           # 18 tests
.\.venv\Scripts\python.exe -m unittest tests.test_transcribe_any_file # import path
.\.venv\Scripts\python.exe -m unittest discover -s tests              # whole suite
.\.venv\Scripts\python.exe verify_transcription.py --quick --no-speakers --seconds 20
```

## 5. The thing to remember

A finished record used to be how the app knew a file had already been transcribed. Now the disk is: `classify_import` falls back to `transcript_exists(media, output_base)`, which looks for `transcripcion.txt` in `<destino>\Transcripciones\<stem>\`. If that check is ever removed, pruning silently turns into "re-transcribe old meetings", which costs hours per file.
