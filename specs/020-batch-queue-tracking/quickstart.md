# Quickstart: validate batch tracking

Prerequisites: Recorder `.venv` (Python 3.11.9). No Transcriptor run is needed for the automated checks — the monitoring loop is driven with a fake process and a log written step by step.

## 1. Automated checks (seconds)

```powershell
$env:QT_QPA_PLATFORM='offscreen'; $env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python.exe -m unittest tests.test_batch_tracking tests.test_cli_progress tests.test_queue_status -v
```

Expected: the batch-tracking cases pass, covering SC-001..SC-006 —

- the live file switches with `> Procesando:` and the previous one becomes ready when its transcript exists (SC-001, SC-002);
- the 90% of the ASR is not carried into speaker identification, where progress is indeterminate (SC-003 side, FR-004);
- a cancelled member is not resurrected when the engine reaches it (FR-009);
- a member the engine skipped without a result returns to the queue (FR-008);
- one file's error stays in its own log section (SC-004);
- work audio of finished jobs is reclaimed while an active job's audio survives (SC-005).

Full suite (must stay green):

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

## 2. Banner rendering (headless, optional)

Build `MainWindow` without `show()` under `QT_QPA_PLATFORM=offscreen` and feed a snapshot with `batch_pos`/`batch_total` set; the notice must read like:

```text
🎙 Transcribiendo…  ·  Parte 2_Reunion Genesis  ·  archivo 4 de 10
```

With `batch_pos`/`batch_total` at 0 (single file) the suffix must be absent. During speaker identification the bar must be indeterminate.

## 3. Real batch (manual, the actual acceptance)

1. Drop 3+ media files with the same settings (language, quality, speakers, output folder) so they share one engine run.
2. While it runs, check that the list shows exactly one `▶ … En curso (NN%)` and the rest `⏳ … En espera`, and that the summary says `1 en curso · N en espera`.
3. Compare the name in the notice with the last `> Procesando:` line of the log:

   ```powershell
   Get-Content "$env:LOCALAPPDATA\MeetingRecorder\transcripts\logs\<log>.log" | Select-String "> Procesando:" | Select-Object -Last 1
   ```

   They must be the same file, and the notice must show its position (`archivo N de M`).
4. When a file finishes, its row must disappear within about a second of `transcripcion.txt` appearing, and a system notification must name it (if the window is not focused) — the notice itself must move on to the next file, not to the one that just finished.
5. Cancel a waiting row: the file in progress must keep going.

## 4. Disk hygiene

```powershell
Get-ChildItem "$env:LOCALAPPDATA\MeetingRecorder\transcripts\work" -Recurse
```

After a session where everything finished, this must be empty (the purge runs at app start). Audit baseline: 468.6 MB were reclaimed on 2026-09-18.
