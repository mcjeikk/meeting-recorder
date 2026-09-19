# Feature Specification: The estimate charges the model load once, not once per file

**Feature Branch**: `025-startup-charged-once`

**Created**: 2026-09-18

**Status**: Draft

**Input**: Manual acceptance of specs 020 and 021 run on 2026-09-18 with real batches (3 samples of 45 s, then 2 samples of 300 s, speakers on, "Usar más CPU"). Every acceptance criterion passed except the accuracy of the finish time: the app promised 40–57 s more than each file actually took, and the error equalled the fixed model-load charge.

## Context

- The finish time comes from `duration of audio × factor + a fixed model-load charge`. The factor is measured and learned per machine (spec 021); the model-load charge is a constant of 40 s.
- The engine loads Whisper and pyannote **once per run** and reuses them for every file in the same run. That is the whole reason compatible jobs are grouped into a single command. The estimate ignores this and charges the load to every file.
- The estimate of the whole batch adds one model load for **each pending file**: with ten files that is nine loads of phantom time.
- Measured on this machine, same configuration, same 45 s of audio: the file that loaded the models took 55 s and 54 s; the file that reused them took 42 s. The load therefore costs about **12–13 s**, not 40 s.
- Consequence on realistic durations (300 s of audio): the app promised 370 s and the files took 313 s and 330 s — an error of +57 s and +40 s, roughly 12–18 % long.
- The error is always in the same direction (promising late), so nothing breaks; but the number is the only answer the app gives to "can I go away and come back?", and it is the second-longest-lived complaint after the frozen percentage.
- The learned history corrects the *factor* after three real samples; it cannot correct the fixed charge, which is added after the multiplication.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The promised time matches a single file (Priority: P1)

As the primary user who leaves the app transcribing I want the promised finish time to be close to reality, so I can decide whether to wait or come back later.

**Why this priority**: The finish time exists precisely so the user can leave. An estimate that is consistently long makes the user wait for nothing, and makes the whole notice look unreliable even when the phase and the percentage are right.

**Independent Test**: Transcribe a file of known duration and compare the first promised time against the real one.

**Acceptance Scenarios**:

1. **Given** a file that runs in an engine that has just started, **When** the notice shows the finish time, **Then** it includes the model load once and lands within a modest margin of the real time.
2. **Given** a file that runs in an engine that already transcribed another file, **When** the notice shows the finish time, **Then** it does not include any model load.
3. **Given** a very short file, **When** the notice shows the finish time, **Then** the promise is not more than double the real time.
4. **Given** the estimate turns out to be short, **When** the time runs out and the file is still working, **Then** the promise moves forward and never sits in the past (unchanged from spec 021).

---

### User Story 2 - The promised time matches a batch (Priority: P1)

As a user who imported several recordings at once I want the batch estimate to reflect that the engine loads its models once for the whole batch.

**Why this priority**: The batch estimate is what the user reads before walking away from a long queue; it is also where the defect multiplies, once per pending file.

**Independent Test**: Queue several compatible files and compare the batch estimate against the sum of the real times.

**Acceptance Scenarios**:

1. **Given** several files queued as one batch, **When** the batch estimate is shown, **Then** the model load is counted at most once for the whole batch.
2. **Given** files that will run as separate engine runs, **When** the estimate is shown, **Then** each run counts its own load.
3. **Given** a file in the batch whose audio duration is unknown, **When** the estimate is shown, **Then** no batch total is shown at all (unchanged from spec 021).

---

### Edge Cases

- A batch where the live file is the last one: nothing pending, so nothing to add.
- A job adopted after the app restarted, in an engine already running: the load is already paid and must not be charged.
- The learned factor already absorbs part of the load for first files (it is measured from real runs that included one): the charge must not be double-counted into the factor's own samples.
- A machine slower at loading than this one: the charge must be a single value that is easy to correct, and a wrong value must degrade the estimate only, never the queue.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The finish-time estimate MUST charge the model-load cost at most once per engine run.
- **FR-002**: A file that runs in an engine that has already transcribed another file MUST NOT be charged any model-load cost.
- **FR-003**: The batch estimate MUST NOT add a model-load cost for each pending file of the same run.
- **FR-004**: The model-load charge MUST reflect what was measured on this machine rather than a guess, and MUST live in one place so it can be corrected.
- **FR-005**: The estimate MUST keep the guarantees of spec 021: it never promises a moment in the past, the percentage keeps advancing during speaker identification, and the bar never reaches 100 % on time alone.
- **FR-006**: Speed samples MUST stay comparable: a sample taken from a file that loaded the models and one that did not MUST NOT be mixed in a way that skews the learned factor.
- **FR-007**: A wrong or missing estimate MUST remain advisory: no queue, retry or process decision may depend on it.
- **FR-008**: The engine MUST NOT be modified.

### Key Entities

- **Engine run**: one invocation of the transcription command, carrying one or more files; pays the model load once, at the start.
- **Model-load charge**: the fixed seconds spent loading the models before the first second of audio is processed.
- **Speed sample**: a measured pair (audio duration, active time) for a configuration, used to learn this machine's factor.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a batch of N compatible files, the batch estimate contains exactly one model-load charge, independent of N.
- **SC-002**: The first estimate of a file that reuses loaded models equals its audio duration times the factor, with no fixed addition.
- **SC-003**: Re-running the acceptance with two samples of 300 s, each file's first promise is within 15 % of its real time (measured before the change: 12–18 % long).
- **SC-004**: For a sample of 45 s, the promise is under twice the real time (measured before the change: 90 s promised against 42 s real).
- **SC-005**: Every guarantee checked in the acceptance of specs 020, 021 and 024 still holds: one live file at a time, no stale name in the notice, the percentage advancing during speaker identification, truthful phase labels.
- **SC-006**: The whole test suite stays green.

## Assumptions

- The engine keeps loading its models once per run and reusing them; this is documented in `CLAUDE.md` and was corroborated by the 2026-09-18 measurements (13 s and 12 s of difference between a file that loads and an equal-length file that reuses).
- A single constant for the load is enough: the per-machine factor is already learned, and the load is a small fixed cost that only matters for short files and long queues.
- Charging the load to the first file of a run and not to the rest is closer to the truth than any average, because the user sees each file's promise separately.
