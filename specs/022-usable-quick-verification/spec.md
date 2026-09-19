# Feature Specification: A quick check that can actually be run

**Feature Branch**: `022-usable-quick-verification`

**Created**: 2026-09-18

**Status**: Draft (clarified 2026-09-18)

**Input**: Audit of 2026-09-18. The project documents a one-minute end-to-end check of the transcription wiring, but running it fails: it picks the most recent recording, sees that a transcript already exists and refuses, telling the user to pass a flag that would **overwrite a real transcript** ("ojo: --quick la dejaría sin hablantes"). In practice the only safety net for the transcription integration cannot be used, which is exactly how the batch-tracking defects reached a 22-hour run unnoticed.

## Context

- The check exists (`verify_transcription.py`) and runs the real path: real queue code, real worker, real engine subprocess. That design is right; what is broken is that it insists on a full real meeting and a real destination.
- A full meeting takes hours (measured ~1.08× the audio), so "quick" cannot mean "the whole file".
- The audit also showed the reverse risk: a verification run must not write into the user's own data. It already used a temporary queue, but it wrote results into the real output folder, and the speed history it now feeds was also being written to the machine's real file.
- The constitution requires that non-trivial changes to recording or transcription be verifiable with the project's own scripts; a script that cannot be run does not satisfy that.

## Clarifications

### Session 2026-09-18

- Q: Should "quick" keep transcribing the whole recording? → A: No. It must take a short slice of a real recording, so the wiring is exercised without hours of work.
- Q: Where should a verification run write? → A: Into throwaway locations only: temporary queue, temporary destination, temporary history. A verification must never modify, overwrite or pollute real transcripts or settings.
- Q: Should the speaker path be verifiable? → A: Yes, on demand — silent speaker degradation (missing token) is a known trap, so there must be a way to check it without transcribing an entire meeting.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Check the wiring in a couple of minutes, safely (Priority: P1)

As the primary user (or an assistant changing this code) I want a single command that proves the whole transcription path still works — command building, audio extraction, the engine subprocess, progress tracking, artifacts, completion — and that finishes in minutes without touching anything of mine.

**Why this priority**: Today the command aborts. This is the only automated end-to-end guard for the integration.

**Independent Test**: Run it right after a session where every recording already has a transcript; it must succeed and leave the real transcripts untouched.

**Acceptance Scenarios**:

1. **Given** every recording already has a transcript, **When** the quick check runs, **Then** it completes successfully instead of refusing.
2. **Given** a quick check has finished, **When** the user inspects their output folder and queue, **Then** nothing was added, overwritten or removed there.
3. **Given** a quick check runs, **When** it finishes, **Then** it reports what it verified (which recording it sampled, how long the sample was, the artifacts produced, and how long it took).
4. **Given** something in the wiring is broken, **When** the check runs, **Then** it fails with the reason and points at the log of that run.
5. **Given** no recording exists at all, **When** the check runs, **Then** it explains that clearly instead of failing obscurely.

---

### User Story 2 - Verify the speaker path on demand (Priority: P2)

As the primary user I occasionally want to confirm that speaker identification still works (the engine degrades silently to "no speakers" when its token is missing), without spending hours.

**Why this priority**: Known trap with a silent failure mode; the fast path deliberately skips speakers, so there must be a way to opt in.

**Independent Test**: Run the check with speakers enabled on a short sample and confirm the result reports how many speakers were detected, or fails clearly if they were dropped.

**Acceptance Scenarios**:

1. **Given** speakers are requested, **When** the check finishes, **Then** it reports the number of speakers found in the sample.
2. **Given** the engine silently produced no speakers, **When** the check finishes, **Then** it reports that as a failure of the speaker path, not as a success.

---

### User Story 3 - Also cover the new progress and estimate wiring (Priority: P3)

As the primary user I want the check to notice if the app stops reporting progress or a finish time, since those are now the visible part of a long job.

**Why this priority**: Spec 020/021 behavior is only unit-tested against a fake process; one real run should confirm the same fields arrive from the real engine.

**Independent Test**: The check asserts that, during the run, it received progress updates naming the sampled file and an expected finish time.

**Acceptance Scenarios**:

1. **Given** a quick check runs, **When** it finishes, **Then** it confirms it received progress updates for the sampled file and a finish-time estimate.
2. **Given** progress updates never arrive, **When** the check finishes, **Then** it reports that as a failure even if the transcript was produced.

---

### Edge Cases

- The chosen recording is shorter than the requested sample: use the whole recording.
- The recording is still being written or locked (OneDrive, antivirus): report a clear, retried failure.
- The engine or its environment is missing: say so instead of hanging.
- The user interrupts: the child process must be reported, not silently left behind.
- The sample must keep the meeting's audio-track layout, so the extraction path (the "Mezcla" track choice) is genuinely exercised.
- Temporary files must be cleaned up on success and kept on failure for diagnosis.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The quick check MUST work on a short sample of a real recording instead of the whole file, with the sample length adjustable.
- **FR-002**: The quick check MUST write exclusively to throwaway locations: its own queue, its own destination folder and its own speed history. It MUST NOT read-modify-write anything in the user's output folder, queue or configuration.
- **FR-003**: The quick check MUST NOT require a flag that risks overwriting existing user transcripts, and MUST NOT refuse to run because a real transcript already exists.
- **FR-004**: The quick check MUST exercise the real path end to end: track selection and audio extraction, command construction, the engine subprocess, progress tracking, and completion by artifacts.
- **FR-005**: The check MUST verify the produced artifacts (text, subtitles, structured data) and report them.
- **FR-006**: The check MUST offer an opt-in speaker verification that fails when speakers were silently dropped.
- **FR-007**: The check MUST confirm that progress updates and a finish-time estimate were received for the sampled file, and fail if they were not.
- **FR-008**: On success the check MUST clean up its temporary files; on failure it MUST keep them and print the location of its log.
- **FR-009**: The check MUST report a bounded total duration and exit with a distinct status for: success, wiring failure, environment missing, timeout, and user interruption.
- **FR-010**: The full-file verification MUST remain available for the cases where transcribing a complete recording is the point.
- **FR-011**: Project documentation MUST describe the runnable command and what it proves.

### Key Entities

- **Verification run**: one execution of the check — the recording it sampled, the sample length, its throwaway locations, the updates it received, the artifacts produced and the verdict.
- **Sample**: a short excerpt of a real recording that keeps the original audio-track layout.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The quick check succeeds on a machine where every existing recording already has a transcript (today it aborts).
- **SC-002**: A quick check with the default sample length finishes in under 5 minutes on the audited laptop, and the fast variant (no speakers) in under 2.
- **SC-003**: After a quick check, the user's output folder, queue and speed history are byte-for-byte unchanged, and no temporary folder is left behind on success.
- **SC-004**: A deliberately broken wiring (missing engine, missing media, no progress updates) is reported as a failure with an actionable message, never as success.
- **SC-005**: When speakers are requested and the engine drops them, the check exits as a failure naming the speaker path.
- **SC-006**: Automated tests cover the decisions the check makes (destination isolation, sample building, verdict rules) without running the engine.

## Assumptions

- At least one real recording exists to sample; the check is a smoke test of the integration, not a synthetic audio generator.
- A short sample is enough to exercise the wiring; it is not a quality benchmark of the transcription itself.
- The sibling engine and its environment are installed as documented; verifying installation is out of scope beyond reporting its absence.
- Progress and estimate checks rely on the fields introduced by specs 020 and 021.
