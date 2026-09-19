# Feature Specification: The notice names the phase that is actually running

**Feature Branch**: `024-truthful-phase-label`

**Created**: 2026-09-18

**Status**: Draft (clarified 2026-09-18)

**Input**: Audit of 2026-09-18 (spec 022 analysis, "Notes for the next feature"). Two real verification runs printed `Audio listo… 4%` and `Audio listo… 35%` while the engine's own log said `- Transcribiendo (modelo large-v3-turbo, idioma es)...`. The percentage and the finish time are now correct (specs 020/021); the words next to them are not.

## Context

- The label comes from `parse_plain_chunk`, which reads the engine's plain log. It reacts to `Convirtiendo audio`, `Audio ya en WAV`, `transcribiendo... NN%`, `-> dispositivo:` and `Identificando hablantes`.
- The engine announces each phase before doing it: `- Transcribiendo (modelo …, idioma …)...` then `- Identificando hablantes (diarizacion)...`. **Neither announcement of transcription is matched**, so the label keeps whatever the previous line left — `Audio listo…`, which is not a phase at all but the note that the WAV did not need converting.
- The transcription percentage only prints on jumps of 10 points or more, so on a short file the stale label can stay for the whole transcription; on a 20 s sample it showed `4%` and `35%`.
- `-> dispositivo: cuda` relabels to `Transcribiendo (GPU)…`, but the engine prints that line *after* transcription returned. The label claims a phase that just ended.
- After `-> N hablante(s) detectado(s)`, the app still says `Identificando hablantes… (la fase más lenta)` while the engine is merging words with speakers and writing the three output files.
- The worker decides the percentage is indeterminate by looking for the word "hablantes" **inside the Spanish label** (`worker._monitor`). Behavior keyed off display text breaks the moment the wording changes.

## Clarifications

### Session 2026-09-18

- Q: Should the label follow the engine's announcements or keep guessing from percentages? → A: Follow the announcements; the engine says what it is about to do.
- Q: What should the label say between "transcription finished" and "speakers finished"/"files written"? → A: Name the real work: writing/assembling the results.
- Q: Keep the GPU mention? → A: Not as a phase label, because it arrives when that phase is over. The device stays in the log.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The notice tells the truth about what is happening (Priority: P1)

As the primary user watching a transcription I want the notice to name the phase that is running right now, so I can tell whether it is preparing audio, transcribing, identifying speakers or finishing.

**Why this priority**: The notice is the only window into a job that lasts as long as the meeting. A wrong phase makes the correct percentage and finish time look wrong too.

**Independent Test**: Replay a real engine log line by line and check the label at each step against what the engine was doing.

**Acceptance Scenarios**:

1. **Given** the engine announced it is transcribing, **When** the notice updates, **Then** it says it is transcribing — without waiting for a percentage.
2. **Given** the audio needed no conversion, **When** the notice updates, **Then** it never shows an audio-preparation label next to a transcription percentage.
3. **Given** the engine announced speaker identification, **When** the notice updates, **Then** it says so and the percentage stops following the transcription figure.
4. **Given** the engine reported the speakers it found (or that transcription ended with speakers off), **When** the notice updates, **Then** it says the results are being written, not that speakers are still being identified.
5. **Given** a file so short that no percentage line is ever printed, **When** the notice updates, **Then** it still names transcription while transcription runs.

---

### User Story 2 - The label is text, not logic (Priority: P2)

As an assistant changing this code I want the progress rules to depend on an explicit phase, not on words in the Spanish label, so that rewording the notice cannot change how progress behaves.

**Why this priority**: Today the "percentage is indeterminate" rule matches the substring `hablantes` in the label. That is a hidden dependency between display text and behavior, and it is exactly how the frozen-90% defect survived so long.

**Independent Test**: Change the user-facing wording in one place and confirm no progress behavior changes and every test still passes.

**Acceptance Scenarios**:

1. **Given** the parser reports a phase, **When** the worker decides whether the percentage applies, **Then** it uses the phase, not the label text.
2. **Given** the wording of a label changes, **When** the suite runs, **Then** nothing about progress or estimates changes.

---

### Edge Cases

- A log chunk containing several phases at once (the engine flushes in blocks): the last phase in the chunk wins, as today.
- A batch where a new file starts mid-chunk: the new file's phases must not be attributed to the previous one.
- The engine's wording changes in a future version: unmatched lines must leave the label unchanged rather than blank it.
- Speakers requested but silently dropped: the note ("sin hablantes") keeps working as today.
- Paused by a recording: the pause label keeps priority over any phase label.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The phase label MUST be driven by the engine's phase announcements, so it names transcription from the moment the engine says it is transcribing.
- **FR-002**: The label MUST NOT show an audio-preparation state once transcription has started, and "the audio needed no conversion" MUST NOT be presented as a phase.
- **FR-003**: The label MUST NOT claim a phase the engine has already reported as finished.
- **FR-004**: There MUST be a truthful label for the final stretch — assembling and writing the results — covering the time after transcription (speakers off) or after the speakers were reported.
- **FR-005**: Speaker identification MUST keep its label and MUST keep making the transcription percentage inapplicable.
- **FR-006**: The parser MUST expose the current phase as an explicit value, and the worker MUST key its progress decisions on that value rather than on the label text.
- **FR-007**: Unrecognised log lines MUST leave the current label and phase unchanged.
- **FR-008**: The device (CPU/GPU) MUST NOT drive the phase label; it remains visible in the log.
- **FR-009**: Existing behavior MUST be preserved: which file is live, percentage resets on file change, the "sin hablantes" note, error attribution per file, and the pause label taking precedence.
- **FR-010**: The engine MUST NOT be modified: this is a reading change on the Recorder side only.

### Key Entities

- **Phase**: what the engine is doing for the live file — preparing audio, transcribing, identifying speakers, writing results. Drives both the label and whether the transcription percentage applies.
- **Label**: the Spanish text shown in the notice and the queue row for a phase. Display only.
- **Log chunk**: the bytes read since the last poll; may contain zero or many phase changes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Replaying the real log of a finished job produces the phase sequence preparing → transcribing → identifying speakers → writing results, with no phase appearing after the engine reported it finished.
- **SC-002**: No emission ever pairs an audio-preparation label with a transcription percentage (the defect observed as `Audio listo… 35%`).
- **SC-003**: With a log that never prints a percentage line, the notice still names transcription during transcription.
- **SC-004**: The progress rule for speaker identification is decided by the phase value; grepping the worker finds no decision based on words from a label.
- **SC-005**: Every existing transcription test keeps passing unchanged in behavior (live file tracking, percentage reset, notes, per-file errors, pause).
- **SC-006**: Changing a label's wording requires touching exactly one place, and the suite stays green.

## Assumptions

- The engine's plain-mode messages stay as documented in `contracts/cli-progress-log.md` (spec 020); this feature only matches more of them.
- The user reads the label as a statement about *now*, not as a log of what happened.
- A brief "writing results" label is worth showing even when it lasts a second: it is true, and it explains the gap before the job disappears from the queue.
