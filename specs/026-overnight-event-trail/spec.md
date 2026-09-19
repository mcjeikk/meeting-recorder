# Feature Specification: An overnight queue leaves a trail you can read in the morning

**Feature Branch**: `026-overnight-event-trail`

**Created**: 2026-09-18

**Status**: Draft

**Input**: The user is about to queue several real meetings and leave the app transcribing overnight, and asked for logging so the run can be reviewed afterwards.

## Context

- Today the app keeps two records of a transcription: the engine's own log per batch (`transcripts\logs\*.log`) and the job record in the queue (`transcripts\queue\*.json`), which holds the **final** state — status, error, note, timestamps, attempts.
- What the user actually saw is **not** recorded anywhere. The notice, the percentage, the promised finish time and the batch position are computed, emitted to the window and forgotten. They are exactly what the last three features changed, and exactly what nobody can review the next morning.
- The worker's own decisions are also unrecorded: which files went into one engine run, when a file was promoted to live, when a file was harvested as ready, when a run was suspended because a recording started, when quality was degraded after an out-of-memory, when a speed sample was learned.
- Verifying the recent work needed a throwaway script that wrapped the worker to capture those emissions. That only works for runs launched from a terminal, not for the app the user actually leaves running.
- A night is the interesting case precisely because nobody is watching: several meetings, several engine runs, possibly an out-of-memory, possibly a suspension, and any of it can end in a state that is hard to explain from the final record alone.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reviewing the night afterwards (Priority: P1)

As the primary user I want the app to record what it showed and what it decided during a long unattended queue, so that the next morning the run can be explained without having been there.

**Why this priority**: This is the only way to answer "did it behave?" for a queue that ran while nobody watched. Without it, a wrong estimate or a mis-tracked batch leaves no evidence and cannot be diagnosed.

**Independent Test**: Queue several files, let them run, then read the trail and reconstruct, per file, the phases, the promised times and the outcome.

**Acceptance Scenarios**:

1. **Given** a queue that ran unattended, **When** the trail is read afterwards, **Then** it shows for each file the phases it went through, the percentages and promised times that were displayed, and how it ended.
2. **Given** several files that shared one engine run, **When** the trail is read, **Then** it shows which files shared the run and in what order they became the live one.
3. **Given** a file that failed or was degraded after running out of memory, **When** the trail is read, **Then** the decision and its reason appear next to the file it affected.
4. **Given** a recording that started while the queue was working, **When** the trail is read, **Then** the suspension and the resumption appear, so time that was not worked is not mistaken for slowness.
5. **Given** a promised finish time and the moment the file actually finished, **When** the trail is read, **Then** both are present so the accuracy can be measured without re-running anything.

---

### User Story 2 - The trail can never hurt the transcription (Priority: P1)

As the user whose meetings are being transcribed I want the diagnostic trail to be irrelevant to the work itself, so that nothing about it can spoil a night of transcriptions.

**Why this priority**: A diagnostic feature that can break the thing it observes is worse than no diagnostic. The queue is the product; the trail is a convenience.

**Independent Test**: Make writing the trail fail in every way available (missing folder, unwritable path, unserialisable value) and confirm the queue behaves exactly as before.

**Acceptance Scenarios**:

1. **Given** the trail cannot be written for any reason, **When** the queue runs, **Then** every file is transcribed exactly as it would have been, with no error shown to the user.
2. **Given** the app runs for many hours, **When** the trail grows, **Then** it stays bounded in size without losing the most recent history.
3. **Given** the trail exists, **When** the app decides anything about the queue, retries, processes or estimates, **Then** it does so without reading the trail.

---

### Edge Cases

- Two app instances: only one owns the queue (single-instance guard plus the worker lock), so only one writes the trail.
- A line half-written when the machine loses power: reading must skip it rather than fail.
- Very long values (paths, error text): recorded as they are; the size cap is what bounds the file.
- The user deletes the trail while the app runs: writing recreates it; nothing depends on its continuity.
- The trail must not become a second copy of the transcript: it records states and decisions, never transcribed content.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The app MUST record every state it shows for a transcription — the phase text, the percentage, the promised finish time, the batch position, the pause flag — with the moment it was shown and the file it referred to.
- **FR-002**: The app MUST record the worker's decisions: the files that make up an engine run, promotion of the live file, early completion of a file, suspension and resumption for a recording, quality degradation after an out-of-memory, failures with their reason, and learned speed samples.
- **FR-003**: Each entry MUST carry a timestamp and identify the file it concerns.
- **FR-004**: Writing the trail MUST NOT be able to interrupt, delay meaningfully or fail a transcription, whatever goes wrong with it.
- **FR-005**: The trail MUST stay bounded in size over long runs while preserving the most recent entries.
- **FR-006**: A corrupt or truncated entry MUST NOT prevent reading the rest.
- **FR-007**: No queue, retry, process or estimate decision may read the trail.
- **FR-008**: The trail MUST stay on this machine, outside any synchronised folder, next to the queue it describes.
- **FR-009**: The trail MUST NOT contain transcribed content.
- **FR-010**: There MUST be a way to read a night's trail as a summary per file, including how accurate the promised times were.

### Key Entities

- **Entry**: one moment in the life of the queue — a state shown, or a decision taken — with its timestamp, kind and the file it concerns.
- **Trail**: the append-only sequence of entries for this machine, bounded in size.
- **Night summary**: the derived reading of a trail — per file, its phases, outcome, real duration and the accuracy of what was promised.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After an unattended queue of several files, the trail alone is enough to state, per file: the phases shown, the outcome, the real duration, and the difference between the first promised finish time and the real one.
- **SC-002**: The trail shows which files shared an engine run and the order in which each became the live file.
- **SC-003**: With writing made to fail, a queue of several files completes exactly as it does today and the user sees no error.
- **SC-004**: Over a run long enough to exceed the size cap, the file stays under it and the most recent entries survive.
- **SC-005**: Reading a trail with a truncated final entry yields every complete entry before it.
- **SC-006**: A night of real meetings can be summarised in one command, without the app running.

## Assumptions

- A few thousand entries per night (one every ten to fifteen seconds per live file, plus decisions) is a negligible amount of data; one entry per line of plain text is enough and needs no database.
- The user is not expected to read the raw trail; the summary is the interface.
- The engine's own logs stay as they are: this feature records the Recorder's side, which is the side that was invisible.
