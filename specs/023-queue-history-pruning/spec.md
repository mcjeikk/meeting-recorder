# Feature Specification: The queue forgets what it no longer needs

**Feature Branch**: `023-queue-history-pruning`

**Created**: 2026-09-18

**Status**: Draft (clarified 2026-09-18)

**Input**: Audit of 2026-09-18. The transcription queue keeps one record per job forever. Three months of use left 64 finished records and 68 log files, and **every** question the app asks the queue — what is pending, what is running, has this file been transcribed, how many are in the batch, what should the list show — re-reads and re-parses all of them. Nothing is ever removed, so the cost of asking grows with every meeting, forever.

## Context

- The queue lives in `%LOCALAPPDATA%\MeetingRecorder\transcripts`: one JSON per job in `queue/`, one log per job in `logs/`. Measured today: 64 records (64 KB) and 68 logs (80 KB) going back to June 10.
- Disk space is *not* the problem: it is under 150 KB. The problem is that the finished records are load-bearing for questions that only concern live work, and they are consulted on a loop while a job runs and on every list refresh.
- Temporary audio is already cleaned up (spec 020 added the orphan work purge), and failed jobs already have a user-facing "clear" action. Finished records are the one thing with no end of life.
- A finished record currently serves a second purpose: it is how the app knows a file was already transcribed, so re-adding it does not spend hours repeating the work. Any pruning has to preserve that answer.

## Clarifications

### Session 2026-09-18

- Q: How much history should be kept? → A: Both bounds: the last 30 days, and at most about 200 records.
- Q: If a pruned file comes back (import or folder), what should happen? → A: Do not re-transcribe it when the transcript already exists on disk — check the output folder instead of relying on the record.
- Q: When should pruning run? → A: Silently at app start, like the orphan audio cleanup already does.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The app stays as fast on month six as on day one (Priority: P1)

As the primary user I want the queue to stay small so that starting the app, importing files and watching a transcription do not get slower the longer I use it.

**Why this priority**: This is the only unbounded growth left in the queue, and it is on the path of every queue question.

**Independent Test**: With a queue holding far more finished records than the limits allow, start the app: the queue shrinks to the limits, the app behaves identically, and nothing the user still needs disappears.

**Acceptance Scenarios**:

1. **Given** finished records older than the age limit, **When** the app starts, **Then** they and their logs are gone.
2. **Given** more finished records than the count limit, **When** the app starts, **Then** only the newest ones within the limit are kept.
3. **Given** a queue already inside both limits, **When** the app starts, **Then** nothing is removed.
4. **Given** pruning runs, **When** the user looks at the app, **Then** there is no message, dialog or delay about it (it is housekeeping, not news).

---

### User Story 2 - An already transcribed file is still recognised after pruning (Priority: P1)

As the primary user I want the app to keep telling me "there is already a transcript of this" when I re-add an old recording, even if its record was pruned — re-transcribing a meeting costs hours.

**Why this priority**: Without this, pruning trades a small slowdown for a large, silent waste of CPU. It is the reason pruning was not simply added earlier.

**Independent Test**: Prune the record of a file whose transcript exists on disk, then import that file again: the app reports the existing transcript and does not queue it.

**Acceptance Scenarios**:

1. **Given** a file whose record was pruned and whose transcript exists on disk, **When** the user imports it, **Then** the app reports the existing transcript and does not queue the file.
2. **Given** a file whose record was pruned and whose transcript was deleted by the user, **When** the user imports it, **Then** it is queued normally.
3. **Given** several files are imported at once, **When** some already have transcripts on disk, **Then** the summary distinguishes queued files from already-transcribed ones exactly as it does today.

---

### User Story 3 - Logs stop accumulating on their own (Priority: P2)

As the primary user (or an assistant diagnosing a failure) I want recent logs to be there and ancient ones to be gone, without having to clean the folder by hand.

**Why this priority**: Logs are the diagnosis path for failures, so they must follow the records rather than be deleted eagerly — but they must not outlive them either.

**Independent Test**: After pruning, every remaining log belongs to a record that still exists, and the logs of live and failed jobs are untouched.

**Acceptance Scenarios**:

1. **Given** a record is pruned, **When** pruning finishes, **Then** its log file is gone too.
2. **Given** a log whose record no longer exists (from an earlier manual cleanup), **When** pruning runs, **Then** that orphan log is removed.
3. **Given** a job that is queued, running or failed, **When** pruning runs, **Then** neither its record nor its log is touched.

---

### Edge Cases

- A record with an unreadable or missing timestamp: treat it as old but never let it break pruning.
- A record whose log is locked (antivirus, still being written): keep going and try again next start.
- The running job's record and log must survive, whatever their age.
- A failed or cancelled record must survive: the user clears those deliberately, and its log is the only explanation of the failure.
- Pruning must never touch the transcripts themselves — only the queue's bookkeeping.
- A pruned record must not make an existing transcript invisible to the import path.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The app MUST remove finished queue records beyond a retention window of 30 days.
- **FR-002**: The app MUST additionally cap the number of finished records kept at about 200, keeping the most recent.
- **FR-003**: Pruning MUST NOT remove records that are queued, extracting, running, failed or cancelled, regardless of age.
- **FR-004**: Pruning MUST remove the log of each pruned record, and MUST remove logs whose record no longer exists.
- **FR-005**: Pruning MUST run automatically and silently when the app starts, and MUST NOT delay startup perceptibly.
- **FR-006**: Pruning MUST NOT touch transcripts, recordings, configuration or the learned speed history.
- **FR-007**: When no record exists for a file, the import path MUST determine "already transcribed" by checking whether the transcript exists in the destination folder.
- **FR-008**: A file recognised as already transcribed MUST NOT be queued, and MUST be reported to the user the same way it is today.
- **FR-009**: Pruning MUST survive unreadable records, locked files and missing folders without raising or aborting the rest of the pass.
- **FR-010**: The limits MUST be stated in one place in the code and documented, so they can be adjusted deliberately rather than guessed.
- **FR-012**: A single pruning pass MUST do a bounded amount of deleting, so that no one startup pays off a large accumulated backlog; the remainder MUST be pruned on following starts until the limits are met.
- **FR-011**: Project documentation MUST describe what the queue keeps and for how long.

### Key Entities

- **Finished record**: a job that completed successfully; history only, never live work. Subject to both limits.
- **Retention limits**: the age window (30 days) and the count cap (200 newest) applied together.
- **Log file**: the engine's output for one job; lives and dies with its record.
- **Existing transcript**: the artifacts in the destination folder; after pruning, they are the authority on "already done".

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With 300 synthetic finished records spread over a year, repeated pruning passes converge to at most 200 records, none older than 30 days, and remove the matching logs.
- **SC-002**: A pass never exceeds its deletion budget, so startup shows no perceptible change even with a large backlog. Measured on the audited laptop: the real queue's first pass removed 33 records and 47 logs in 20 ms, a converged pass costs 3 ms, and asking the queue anything costs ~0.06 ms per stored record (2 ms at 31 records, 37 ms at 600). Freshly written files delete far slower (~16 ms each, antivirus inspecting every unlink), which is what the per-pass budget guards against.
- **SC-003**: Live, failed and cancelled records and their logs are byte-for-byte unchanged by pruning.
- **SC-004**: After pruning the record of an already-transcribed file, importing that file reports the existing transcript and queues nothing.
- **SC-005**: After pruning, no log remains whose record is gone.
- **SC-006**: Repeated pruning on an already-pruned queue removes nothing and reports nothing.

## Assumptions

- 30 days and 200 records are generous for one user: the current three months of real use produced 64 records.
- The destination folder is reachable when checking for an existing transcript; if it is not, treating the file as not transcribed (and queueing it) is the acceptable failure.
- Finished records carry no information the user consults directly: the queue list already hides them (spec 020).
- Failed records keep their existing manual "clear" action; automatic pruning deliberately stays out of that decision.
