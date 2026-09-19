# Feature Specification: Truthful tracking of a multi-file transcription batch

**Feature Branch**: `020-batch-queue-tracking`

**Created**: 2026-09-18

**Status**: Draft

**Input**: User description: "puse a transcribir 10 archivos, pero en la lista sigue apareciendo que el primer archivo está al 90% lo cual es falso… haciendo seguimiento de las transcripciones generadas ya le faltaba una cuando tomé la foto… no está haciendo buen seguimiento de lo que está procesándose, de lo que está completado, de hecho en el aviso de abajo que dice que está transcribiendo aún me sale el nombre de una reunión que procesó hace rato… no es la que estaba procesando en ese momento." Plus the audit of 2026-09-18 (per-file outcome attribution, leftover working audio).

## Clarifications

### Session 2026-09-18

Observed with a real 10-file batch (22.5 h of processing, one shared engine run): the list showed every file as "En curso", the first one frozen at 90%, the notice named the file that had finished hours earlier, and the summary said "10 en curso" when only one was left.

- Q: What is the single source of truth for "which file is being transcribed now"? → A: The engine's own output naming the current file; not the queue order and not the first file of the batch.
- Q: When is a file considered finished? → A: As soon as its transcript exists, without waiting for the rest of the batch.
- Q: Should the notice jump to each file that finishes? → A: No. The notice must stay on the file being processed; finished files are announced separately (system notification) and leave the pending list.
- Q: What does the percentage mean during speaker identification? → A: Nothing measurable yet — it must be shown as indeterminate instead of keeping the previous number (weighted progress and ETA are a separate feature).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Know what is actually happening in a long batch (Priority: P1)

As the primary user I drop ten meetings at once and leave the machine working overnight. At any moment I want to open the app and see, truthfully: which file is being transcribed right now, how far into the batch it is, which files are already done, and which are still waiting.

**Why this priority**: This is the reported defect. A batch runs for a day; wrong status makes the user distrust the queue and re-run work that was already finished.

**Independent Test**: Queue several compatible files, let the engine advance, and compare the app's display against the transcripts appearing on disk and the engine's current file.

**Acceptance Scenarios**:

1. **Given** a batch of 10 queued files, **When** the engine is on the fourth file, **Then** exactly one row shows "En curso" (the fourth), the other pending ones show "En espera", and the notice names that fourth file with its position in the batch.
2. **Given** the engine finishes a file, **When** its transcript exists, **Then** that file is marked ready and leaves the pending list without waiting for the rest of the batch.
3. **Given** the percentage reached 90% on one file, **When** the engine moves to the next file, **Then** the percentage restarts for the new file instead of carrying the previous number.
4. **Given** the engine enters speaker identification, **When** no measurable percentage exists, **Then** progress is shown as indeterminate and the stage is named.
5. **Given** several files finished while the user was away, **When** they look at the summary, **Then** the counts of in-progress, waiting and failed match the real state of the queue.

---

### User Story 2 - Each file's outcome is its own (Priority: P2)

As the primary user, when one file of a batch fails (out of memory, a broken media file), I expect the other files to be unaffected: same quality settings, same speaker identification, no bogus error text copied from a different meeting.

**Why this priority**: A batch shares one engine run and one log. Attributing one file's failure to all of them silently degrades good files (dropping speakers) or marks them failed, which costs hours of reprocessing.

**Independent Test**: Simulate a batch log where only the middle file errors, and confirm the other files' outcomes and settings are untouched.

**Acceptance Scenarios**:

1. **Given** a batch where the second file fails with out-of-memory, **When** outcomes are resolved, **Then** only that file is retried in a lighter configuration; the rest keep their settings.
2. **Given** a batch where the last file dies during speaker identification, **When** outcomes are resolved, **Then** only that file is retried without speakers, and the others keep their speaker labels.
3. **Given** a file the engine never reached (the run ended early), **When** outcomes are resolved, **Then** it returns to the queue with a reason that says so, not another file's error.
4. **Given** the user cancels a file, **When** the engine later reaches that file's name, **Then** the file stays cancelled and is never shown as in progress again.
5. **Given** the user cancels a file that is only waiting, **When** the cancellation is applied, **Then** the file currently being transcribed is not interrupted.

---

### User Story 3 - The queue does not leave junk behind (Priority: P3)

As the primary user I should not find hundreds of megabytes of intermediate audio from meetings transcribed days ago.

**Why this priority**: Real leftovers of 468 MB were found from two finished jobs; the cleanup is best-effort and can fail silently while nothing ever retries it.

**Independent Test**: Leave working audio for a finished job, start the app, and confirm the space is reclaimed while an active job's audio is preserved.

**Acceptance Scenarios**:

1. **Given** working audio belonging to finished, failed or unknown jobs, **When** the app starts, **Then** that audio is deleted and the space reported as reclaimed.
2. **Given** working audio of a job that is still queued or running, **When** the app starts, **Then** that audio is preserved.

---

### Edge Cases

- App closed mid-batch and reopened: the still-running engine is re-adopted and tracking resumes on the file it is actually processing, including the files already finished in the meantime.
- The engine skips a file without producing a transcript: the file returns to the queue for retry instead of being reported ready or failed with someone else's error.
- Process identifiers get reused by the operating system: grouping files of a batch must not attach unrelated historical jobs.
- A recording starts mid-batch: tracking keeps showing the paused state for the current file (recording always wins).
- Names with accents, brackets and spaces (real meeting titles) must match the engine's current-file output.
- A single-file job must not show batch position at all.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The queue MUST show exactly one file as in progress per running engine batch; other queued members MUST be shown as waiting.
- **FR-002**: The file shown as in progress MUST be the one the engine reports it is processing.
- **FR-003**: A file MUST be marked ready as soon as its transcript exists, without waiting for the rest of the batch, and MUST then disappear from the pending list.
- **FR-004**: Progress percentage MUST belong to the file in progress: it MUST reset when the engine switches file and MUST be shown as indeterminate while no measurable percentage exists (e.g. speaker identification).
- **FR-005**: The status notice MUST name the file in progress and, inside a batch, its position and the batch size.
- **FR-006**: The queue summary counts (in progress / waiting / failed) MUST match the real state; a batch MUST NOT be reported as N in progress.
- **FR-007**: Failure analysis MUST be attributed per file: one file's error, out-of-memory or speaker-identification failure MUST NOT change the outcome, retry decision or quality settings of other files in the same batch.
- **FR-008**: A file with no output that the engine never processed MUST return to the queue with a reason describing that, and failure reasons MUST be human-readable (never a raw exit code placeholder).
- **FR-009**: A cancelled or failed file MUST NOT be promoted back to in progress when the engine touches it; cancelling a waiting file MUST NOT interrupt the file being transcribed.
- **FR-010**: Each finished file MUST be announced when the app is not in focus, even if the batch continues.
- **FR-011**: Stale import hints MUST NOT remain visible while transcription is in progress.
- **FR-012**: Intermediate working audio of finished, failed, cancelled or unknown jobs MUST be reclaimed automatically at app start, and MUST be preserved for jobs still queued or running.
- **FR-013**: Selecting a row of the queue MUST NOT redirect the notice away from the file in progress, and refreshing the list MUST NOT leave the selection pointing at a finished file.

### Key Entities

- **Queue job**: one media file to transcribe, with its state (waiting, in progress, ready, failed, cancelled), its quality settings captured at enqueue time, its output location, and the batch run it belongs to.
- **Batch run**: the set of queued jobs handed to a single engine run because their settings are compatible; has an order (the order the engine processes them) and one shared progress record.
- **Progress record**: the engine's own account of what it is doing — the current file, the stage, and a percentage when one exists.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a batch of N files, at any moment exactly one file is displayed as in progress and it is the file the engine names; the count of files displayed as ready equals the number of transcripts on disk.
- **SC-002**: A finished file disappears from the pending list within one status refresh (about one second) of its transcript appearing, instead of at the end of the batch (previously up to 22 hours later).
- **SC-003**: The notice never names a file whose transcript already exists.
- **SC-004**: With a batch log in which exactly one file fails, zero other files in that batch change state, retry count or quality settings.
- **SC-005**: After a session where all jobs finished, leftover intermediate audio is 0 bytes.
- **SC-006**: Automated tests drive the real monitoring loop over a batch log and cover: file switching, ready-on-transcript, indeterminate progress during speaker identification, cancelled-not-resurrected, skipped-file requeue, and per-file failure attribution.

## Assumptions

- The engine keeps printing which file it is processing and a coarse percentage for the transcription phase; richer progress (weighted phases, ETA) is a separate feature.
- A batch is processed strictly in the order the files were handed to the engine.
- Only one app instance drains the queue (existing single-instance lock).
- The notice shows one file at a time; a full multi-file dashboard is out of scope.
- Cancelling a waiting member of a running batch cannot stop the engine from spending time on that file; its result is simply discarded.
