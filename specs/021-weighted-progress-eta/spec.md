# Feature Specification: Progress that means something, and a time estimate

**Feature Branch**: `021-weighted-progress-eta`

**Created**: 2026-09-18

**Status**: Draft (clarified 2026-09-18)

**Input**: Audit of 2026-09-18: the percentage shown while transcribing only measures the transcription phase, in 10-point steps, and says nothing during speaker identification — which is the long phase. After spec 020 the number no longer lies about *which* file it belongs to, but it still does not tell the user how far along the work is or when it will be done. A batch of 10 meetings ran for 22.5 hours with no idea of the remaining time.

## Context from measurements

Measured on the user's laptop (no dedicated GPU) from 22 real meetings, comparing each file's audio duration against its processing time:

- Processing takes about **1.11×** the audio duration (minimum 1.00×, p25 1.05×, p75 1.23×, maximum 1.89×).
- 37.1 hours of audio took 42.3 hours of processing.
- `CLAUDE.md` still claims "2–2.5× the audio duration", which is stale and must be corrected as part of this feature.

This makes a useful estimate possible from a known input: the audio duration of each queued file.

Measured per configuration (same 22 meetings, joined with each job's settings):

| Quality / PC usage | Samples | Median factor | Range |
|--------------------|---------|---------------|-------|
| Equilibrado (turbo + speakers), more CPU | 18 | 1.08× | 1.00–1.89× |
| Equilibrado (turbo + speakers), keep PC usable | 2 | 1.45× | 1.11–1.80× |
| Rápido (no speakers) | 0 | — | no history yet |
| Máxima calidad (heavier model) | 0 | — | no history yet |

## Clarifications

### Session 2026-09-18

- Q: What should be shown while transcribing? → A: Both — a weighted percentage that keeps moving through every phase **and** a time estimate.
- Q: Where does the speed estimate come from? → A: Hybrid — start from the measured factor for that configuration and learn from this machine's own history as samples accumulate.
- Q: How is the time presented? → A: As the expected finish time ("listo ~21:40"), which is what matters when deciding whether to leave the machine running overnight.
- Q: Where does the batch total go? → A: In the queue summary line, next to the batch position; the main notice stays about the file in progress.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Know how long this will take (Priority: P1)

As the primary user I queue one or more meetings and want to know, without watching logs, roughly how much longer the work needs — so I can decide whether to leave the laptop on, keep working on it, or start the batch overnight.

**Why this priority**: This is the practical question the current display cannot answer. The percentage stalls at 90% and then spends hours in speaker identification.

**Independent Test**: Queue a file of known duration and compare the shown estimate against the actual finish time.

**Acceptance Scenarios**:

1. **Given** a queued file whose audio duration is known, **When** transcription starts, **Then** an estimate of the remaining time for that file is shown.
2. **Given** the file is in speaker identification, **When** the user looks at the notice, **Then progress keeps advancing (no frozen number) and the estimate keeps decreasing.
3. **Given** a batch of several files, **When** one finishes, **Then** the estimate for the whole batch decreases accordingly.
4. **Given** an estimate was shown, **When** the file finishes, **Then** the real duration was within a stated tolerance of the estimate for the majority of runs.

---

### User Story 2 - A percentage that reflects real work (Priority: P2)

As the primary user I want the progress indicator to move roughly in proportion to the work left, instead of racing to 90% and then stalling for hours.

**Why this priority**: Without it, the percentage trains the user to distrust the app; with it, the bar itself becomes the estimate's sanity check.

**Independent Test**: Feed a recorded batch log through the progress computation and confirm the resulting percentage advances monotonically across phases.

**Acceptance Scenarios**:

1. **Given** the transcription phase is at 100%, **When** the file moves to speaker identification, **Then** overall progress for that file is below 100% and keeps increasing.
2. **Given** a file skips speaker identification (fast preset or degraded retry), **When** transcription completes, **Then** progress reaches 100% without waiting for a phase that will not run.
3. **Given** progress was computed for a file, **When** the engine switches file, **Then** progress restarts for the new file (spec 020 behavior is preserved).

---

### Edge Cases

- Audio duration unknown or unreadable (corrupt media, still extracting): show the phase without inventing an estimate.
- The machine is slower or faster than the historical factor (background load, recording pauses): the estimate must adapt rather than count down into negative time.
- Transcription is suspended because a recording started: the estimate must not keep counting down while no work happens.
- Speaker identification is skipped or fails and the file is retried without it: the estimate must be recomputed, not kept from the previous attempt.
- The first run on a new machine has no history to learn from.
- Very short files (a 30 s clip): fixed overhead (model loading) dominates and must not produce an absurd estimate.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST show, for the file in progress, the expected finish time based on its audio duration and a processing speed factor.
- **FR-002**: The system MUST show overall progress per file that accounts for every phase that will actually run, so it advances during speaker identification instead of stalling.
- **FR-003**: Progress MUST never decrease within a file's attempt, and MUST reset when the engine switches file (preserving spec 020).
- **FR-004**: When a file's audio duration is unknown, the system MUST show the phase and omit the estimate rather than guess.
- **FR-005**: While transcription is suspended (recording in progress), the estimate MUST be frozen and labelled as paused.
- **FR-006**: For a batch, the queue summary MUST show the expected finish time of the whole run, alongside the batch position; the main notice stays about the file in progress.
- **FR-007**: The estimate MUST degrade gracefully when reality diverges: it MUST be revised as the run progresses and MUST never display negative or already-past times.
- **FR-008**: The speed factor MUST come from this machine's own completed transcriptions for the same configuration (quality preset and PC-usage choice) once enough samples exist, and from a documented measured default before that. History MUST stay local and MUST survive app restarts.
- **FR-009**: Times MUST be shown as an expected finish clock time, rounded so they do not imply false precision, and MUST make the day explicit when the finish falls outside today.
- **FR-010**: The file in progress MUST show both a weighted percentage (advancing through every phase) and its expected finish time in the transcription notice; the queue summary MUST carry the batch total.
- **FR-011**: Project documentation MUST be corrected to the measured factors (`CLAUDE.md` claims 2–2.5×; the Equilibrado preset hint claims ~2×; measured median is 1.08× with more CPU and 1.45× keeping the PC usable).

### Key Entities

- **Audio duration**: the length of the media to transcribe; the input the estimate is built on.
- **Speed factor**: processing time per unit of audio, per quality preset and PC-usage profile; measured from completed jobs.
- **Phase weights**: the share of a file's work taken by audio preparation, transcription and speaker identification.
- **Estimate**: remaining time for the file in progress and for the batch, revised as the run advances.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For files longer than 10 minutes, the estimate shown at the start is within ±25% of the real duration in at least 3 of 4 runs (the measured p25–p75 band is 1.05×–1.23×).
- **SC-002**: The progress indicator advances at least once every 2 minutes during speaker identification (no multi-hour stall).
- **SC-003**: Overall progress per file is monotonic: no test run shows it going backwards inside an attempt.
- **SC-004**: When audio duration is unknown, no estimate is shown and the stage is still named.
- **SC-005**: A user can answer "will this be done before I need the laptop?" from the notice alone, without opening logs.
- **SC-006**: Automated tests cover: weighting across phases, estimate revision, paused state, unknown duration, skipped speaker phase, and the batch total.
- **SC-007**: After three completed files with the same configuration, the factor used comes from this machine's own measurements rather than the default, and persists across restarts.
- **SC-008**: Finish times are rounded to whole 5-minute marks and state the day when it is not today; no displayed finish time is ever in the past.

## Assumptions

- Audio duration is available for queued media (the work audio is produced by the recorder's own extraction step, and finished transcripts already record duration).
- Speaker identification remains the dominant phase and the transcription phase keeps reporting coarse percentages (spec 020 contract).
- Estimates are advisory: no behavior (scheduling, retries) depends on them.
- Presentation stays inside the existing notice and queue list; no new window or dashboard.
- The historical factor is machine- and preset-specific; it is not shared or uploaded anywhere (constitution II).
