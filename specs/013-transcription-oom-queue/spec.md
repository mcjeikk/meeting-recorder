# Feature Specification: Survive OOM and Show the Real Queue

**Feature Branch**: `013-transcription-oom-queue`

**Created**: 2026-09-08

**Status**: Draft

**Input**: User dropped three interview files; transcription “does nothing”, takes forever, queued items vanish. Logs: Máxima calidad (`large-v3`) + `pc_impact=full`. Parte 2 `Unable to allocate 973 MiB`. Parte 1 `mkl_malloc: failed to allocate memory` then a second `transcribe.py` on the same WAV after the UI crashed. Parte 3 still `pending`. Two Recorder processes. UI only shows the last job snapshot.

## Clarifications

- Q: Did the three files leave the durable queue? → A: No. They are still in `%LOCALAPPDATA%\MeetingRecorder\transcripts\queue`. The banner only shows one job, so the others look gone.
- Q: Why no progress? → A: Out of memory on `large-v3` for long interviews; retries used the same heavy settings. After UI crash, a second Transcriptor was spawned on the same WAV.
- Q: Should Máxima still be allowed? → A: Yes, but OOM must auto-lighten (no speakers, then turbo) instead of failing silently / retrying the same job. One Transcriptor per file.

## User Scenarios

### US1 — Memory failure becomes a lighter retry (P1)

Long file + Máxima runs out of RAM. The app must retry lighter (no speakers, then lighter model) with a visible reason, not sit on `running` or vanish.

### US2 — No second engine on the same file (P1)

If a Transcriptor for that WAV is already alive (after a UI crash), the Recorder must adopt it, not start another.

### US3 — See the whole open queue (P2)

Banner shows current job **and** how many are waiting / failed so dropping three files does not look like two disappeared.

## Requirements

- **FR-001**: Detect allocation failures (`Unable to allocate`, `mkl_malloc`, `MemoryError`, `failed to allocate memory`) from the job log.
- **FR-002**: On OOM, requeue lighter: first `--no-diarize` + usable PC; if still `large-v3`, switch to `large-v3-turbo`. Fail only when already on the lightest path.
- **FR-003**: Before launching CLI, if a `transcribe.py` already has that work WAV (or stem) in its command line, adopt that process; terminate extra duplicates of the same WAV.
- **FR-004**: Reconcile after restart must use FR-003, not only the stored PID (PIDs recycle).
- **FR-005**: The UI MUST list each open/failed job with a plain-language status (waiting / in progress / failed) in section 4. Dropping three files MUST show three rows. The banner of the selected job is extra, not the only status.
- **FR-006**: Only one Recorder UI should process the queue (existing lock stays; add a process mutex so a second `pythonw -m app.main` does not sit idle and confuse the user).

## Success Criteria

- **SC-001**: OOM log snippet is classified as memory failure in unit tests.
- **SC-002**: Degrade path from Máxima+speakers → no speakers → turbo is unit-testable on a job object.
- **SC-003**: After drop of 3 files, the user sees 3 named rows (waiting/in progress), not only the last banner title.
