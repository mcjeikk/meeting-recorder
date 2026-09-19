# Feature Specification: A momentary file lock must not fail a transcription

**Feature Branch**: `027-queue-record-contention`

**Created**: 2026-09-18

**Status**: Draft

**Input**: The trail added by spec 026 recorded, on its very first real batch, a job marked as failed with `PermissionError: [WinError 5] Acceso denegado: '...\queue\5dcf67660ae2.json.tmp'`. The file was transcribed correctly on the retry, so nothing was lost — and nothing would ever have revealed it either.

## Context

- Each job is one JSON file in the queue, written atomically: text into a temporary file, then an atomic replace. That protects against power loss, which is what it was designed for.
- The temporary file had a **fixed name per job**. Two threads save the same job routinely: the window (Qt) when the user changes something, and the worker while it tracks progress. With one name, they write the same temporary file and the replace can fail.
- On Windows, the replace can also fail for reasons outside the app: antivirus or the indexer holding the file for an instant.
- A failure to save surfaced as a job failure, consuming one of its three attempts. Three unlucky moments in one night and a real meeting ends in "Falló" with a message about a temporary file, which says nothing to the user.
- The same race has a **reading** side: while one thread replaces the file, another thread's read can be denied. The reader treated any failure as "corrupt record" and returned nothing — and a job that reads as absent is a job that can be queued a second time, because deduplication asks whether a record exists.
- Neither side was visible before: the queue record keeps the final state, and this kind of failure leaves no trace in it once the retry succeeds.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A locked file costs a moment, not a meeting (Priority: P1)

As the user leaving a long queue unattended I want a momentary lock on a queue record to be retried, so that no meeting ends as failed because a file was busy for an instant.

**Why this priority**: It attacks the queue's own bookkeeping, at night, unattended, and it presents itself to the user as a failed transcription with an incomprehensible reason.

**Independent Test**: Make the replace fail a couple of times and confirm the record is still saved and the job unaffected.

**Acceptance Scenarios**:

1. **Given** the record cannot be replaced for an instant, **When** the app saves it, **Then** it retries briefly and the save succeeds, with no visible effect on the job.
2. **Given** two threads save the same job at the same time, **When** both write, **Then** neither interferes with the other and the record stays valid.
3. **Given** the record genuinely cannot be written, **When** the retries run out, **Then** the failure is reported rather than silently dropped, because a status change that vanishes is worse than a visible error.
4. **Given** any save attempt failed, **When** it is over, **Then** no temporary file is left behind in the queue.

---

### User Story 2 - A busy record is not an absent record (Priority: P1)

As the user importing files I want a momentarily locked record to be read as what it is, so that a busy file is never mistaken for a missing one.

**Why this priority**: Deduplication and status decisions ask whether a record exists. "Absent" is a meaningful answer, and a lock must not fake it — the cost would be transcribing the same meeting twice, or a job appearing to disappear from the queue.

**Independent Test**: Deny the read for an instant and confirm the record is still returned.

**Acceptance Scenarios**:

1. **Given** a record is locked for an instant, **When** it is read, **Then** the read is retried and the record is returned.
2. **Given** a record does not exist, **When** it is read, **Then** the answer is immediate — absence is an answer, not an obstacle.
3. **Given** a record is genuinely corrupt, **When** it is read, **Then** it is ignored exactly as before, without breaking the rest of the queue.

---

### Edge Cases

- A stray temporary file in the queue folder must never be read as a job.
- A crash between writing the temporary file and replacing it: the previous record stays intact, as it does today.
- Several app instances: prevented elsewhere (single-instance guard plus the worker lock), so this is about threads, not processes — but the temporary name must still be unique per process for the case of a second process being started anyway.
- The retry budget must stay short enough that it cannot stall the window: this runs on the Qt thread too.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Saving a queue record MUST survive a momentary failure to replace it by retrying for a short, bounded time.
- **FR-002**: Two concurrent saves of the same job MUST NOT interfere; each MUST use its own temporary file.
- **FR-003**: A save that cannot succeed MUST report the failure to its caller.
- **FR-004**: No temporary file may remain in the queue after any save, successful or not.
- **FR-005**: Reading a record MUST survive a momentary failure by retrying for the same bounded time.
- **FR-006**: The absence of a record MUST be answered immediately, without retries.
- **FR-007**: A genuinely corrupt record MUST keep being ignored without affecting other records.
- **FR-008**: The retry budget MUST be short enough not to freeze the window, since saving also happens on the interface thread.
- **FR-009**: Temporary files MUST NOT be readable as jobs.

### Key Entities

- **Queue record**: the JSON file describing one job; the unit of atomic write.
- **Temporary file**: the file a save writes before replacing the record; must belong to exactly one writer.
- **Retry budget**: the short window during which a momentary lock is tolerated.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With the replace failing twice in a row, the record is saved and the job's state is exactly what was saved.
- **SC-002**: Six threads saving the same job a hundred times between them produce no errors, a valid record, and no leftover temporary files.
- **SC-003**: With the read denied twice in a row, the record is returned rather than reported absent.
- **SC-004**: Reading a record that does not exist returns immediately, with no retry delay.
- **SC-005**: A permanent write failure raises, and leaves no temporary file.
- **SC-006**: A stray temporary file in the queue folder does not change the number of jobs the queue reports.

## Assumptions

- These locks last milliseconds (another thread's replace, an antivirus scan), so a budget of a few tenths of a second covers them without a perceptible delay anywhere.
- Retrying is the right answer for a lock and the wrong answer for absence; the two cases must stay distinguishable, which is why they are handled separately rather than by catching everything.
- The learned speed history has the same fixed-temporary pattern, but a failure there is already swallowed by design (the history is a convenience, not a record), so it is out of scope.
