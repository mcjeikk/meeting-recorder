# Research: Truthful tracking of a multi-file transcription batch

## R0. What the real 10-file run proves

**Evidence** (`...\transcripts\logs\Parte 2_…-20260916_102253_2b6d76b44ab5.log`, 10.4 KiB): header `--- intento 1 · 10 archivo(s) ---`, then ten `> Procesando: <stem>.wav` sections, 99 `transcribiendo... NN%` lines (10 per file, one every 10%), ten `OK en …s` lines summing 80 913 s (22.5 h), `Finalizado. 10/10`. The ten queue JSONs all carried the same pid (20708) and the same `log_path`.

**Conclusion**: the log already contains everything needed for truthful tracking (current file, phase, coarse percentage, per-file completion). The defect was entirely on the Recorder side: it monitored the batch leader and ignored the file switches.

## R1. Which job is "in progress"

**Decision**: The CLI's `> Procesando: <name>.wav` line is the single source of truth. `cli_progress.job_for_cli_name()` matches it against each job's `work_wav` name (fallback: `media stem + ".wav"`). Exactly one job is `running`; the rest of the batch stays `pending` until its turn.

**Rationale**: The work WAV is created as `work/<job id>/<media stem>.wav`, so the CLI's printed name maps 1:1 to a job even with accents, brackets and spaces (`élite [PAP-OP-MONETIZACIÓN]-20260916_140659.wav`). Keeping non-live members `pending` makes the existing list/summary code truthful with no extra state.

**Alternatives considered**:

| Option | Why rejected |
|--------|----------------|
| Keep all members `running`, add a `live` flag to each job | Extra persisted state to keep consistent after crashes; the queue already has a state that means "not yet started" |
| Infer the current file from the argv order + count of finished transcripts | Breaks the moment a file fails or is skipped; also wrong while a file is being written |
| Ask the Transcriptor for machine-readable progress (JSON lines) | Changes the sibling project's contract for a cosmetic gain; the plain text already suffices (constitution III) |

**Risk accepted**: while `_execute` is inside `_monitor`, the other members are `pending` but `_next_job()` is not reachable (the worker thread is blocked), so nothing starts a second CLI for them. On restart, reconcile re-adopts by pid and groups the cohort by pid, so the pending members are not launched again either.

## R2. When a file is "ready"

**Decision**: Poll for `transcripcion.txt` in each member's result folder (`_harvest_ready`) and settle that job immediately, without waiting for the run to exit.

**Rationale**: In a batch the exit code is global (constitution III / CLAUDE.md), so artifacts are already the success criterion. Waiting for the process meant a file finished at hour 2 stayed "En curso" until hour 22. Polling N paths once per second is negligible next to the transcription itself.

**Alternatives considered**: parsing `OK en …s -> <folder>` from the log (would work, but it is cosmetic text and the artifact check is the authoritative one we already trust); filesystem watchers (more machinery for a 1 s poll).

## R3. What the percentage means

**Decision**: `parse_plain_chunk` returns the percentage of the current file; a file switch resets it to 0, and diarization returns `-1`, which the worker maps to "no number" so the UI shows an indeterminate bar with the stage named.

**Rationale**: The ASR emits 10 points per file; the number belonged to whichever file the engine was on. Carrying 90% into the next file (or into diarization, which is the long phase) is the visible lie the user reported. Making it indeterminate is honest; turning it into a *meaningful* overall percentage requires weighting the phases and is deliberately a separate feature.

**Alternatives considered**: freeze the last value during diarization (still reads as "almost done" for hours); estimate diarization progress from elapsed time (needs measured factors — separate feature).

## R4. Attributing failures inside a shared log

**Decision**: `log_section_for(text, name)` slices the log between that file's `> Procesando:` line and the next one. `_settle` then uses only that slice for the error line, the OOM check and the "died in diarization" check. An empty slice means the file never started.

**Rationale**: `_settle` previously read the whole log, so one file's `[X] Error con …` / `Unable to allocate …` decided the retry strategy for every other member: good files could be re-queued with `no_diarize=True` (losing speakers) or marked failed with another meeting's error text. With 10 files per run and 2 attempts each, that is hours of wasted CPU and a silently degraded result.

**Alternatives considered**: one log file per job (loses the single-run advantage of shared model loading, and the CLI writes one stream); trusting the global exit code (it says nothing about which file failed).

## R5. Cancellation inside a batch

**Decision**: Cancelling kills the child process only when the cancelled job is the live one. A cancelled/failed/done job is never promoted back to `running`, even if the CLI later prints its name.

**Rationale**: Previously cancelling any member killed the whole run (losing the file in progress). And with file-switch promotion added, a cancelled member would have been resurrected when the engine reached it.

**Accepted limitation**: the file is already in the CLI's argv, so the engine will still spend time on it; its output is simply discarded. Skipping mid-argv would require an engine-side feature.

## R6. Leftover working audio

**Decision**: `JobStore.purge_orphan_work_dirs()` at reconcile deletes `work/<id>` for jobs that are done/failed/cancelled/unknown, preserving directories of jobs still queued or running; returns bytes reclaimed.

**Rationale**: `_cleanup_wav` is best-effort (`except OSError: pass`) because the CLI may still hold the handle; nothing ever retried. Audit found 468.6 MB in two directories from jobs finished days earlier. 16 kHz mono WAV of a 1 h meeting is ~115 MB, so this grows fast.

**Alternatives considered**: delete by age (age is not the question — job state is); retry cleanup in a timer (arrival at app start is enough for a desktop app and costs nothing).

## R7. Banner vs. list selection

**Decision**: The banner follows the live job. List refresh selects the live row unless the user deliberately selected a failed/cancelled row (so Reintentar / Ver log still work). Selecting a *waiting* member does not redirect the banner.

**Rationale**: The old refresh restored the previous selection with signals blocked, so the banner and the list could describe different files — part of the reported confusion ("me sale el nombre de una reunión que procesó hace rato").

## R8. Out of scope here

Weighted progress / ETA, queue history pruning, and making `verify_transcription.py --quick` runnable are separate features (they were raised by the same audit and have their own specs).
