# Feature Specification: Keep the PC Usable During Transcription

**Feature Branch**: `011-transcription-pc-impact`

**Created**: 2026-09-08

**Status**: Draft

**Input**: User description: "Cuando empiezo a transcribir los audios o videos, se me congela tanto el computador que se me bloquean otras aplicaciones. Si por mi fuera usaría el mejor modelo, sin embargo estoy usando el equilibrado. ¿Hay alguna forma para gestionar esto?"

## Clarifications

### Session 2026-09-08

Decisions encoded from the user request, constitution (Recording Always Wins; sibling subprocess; simplicity for one power user), and how Equilibrado actually behaves today. Not blocked on interactive Q&A.

- Q: Is the freeze “solved” by switching to Rápido? → A: No. Rápido only skips speaker labels. Equilibrado already uses the same recognition class as Rápido plus speaker labeling, which is the heavy phase. The user wants **quality and a usable PC at the same time**, including the option to pick Máxima calidad.
- Q: Should quality and machine impact be the same control? → A: No. They are independent. **Velocidad / calidad** stays (Rápido / Equilibrado / Máxima). A new **Uso del PC** control chooses whether transcription must leave the rest of the computer responsive, or may take almost all CPU when the user is away.
- Q: What is the default after this feature? → A: **Dejar el PC usable**. The reported pain is a frozen desktop, not a slow transcript. Existing queued jobs that were created before this field existed keep the previous “use most cores” behavior so an in-flight job does not silently change mid-queue.
- Q: Must the user edit Transcriptor config files? → A: No. The Recorder UI is the only setting. The sibling tool still runs as a subprocess.
- Q: Does this replace Recording Always Wins? → A: No. An active recording still pauses transcription completely. This feature is about leaving *other* apps usable while a job is running and the user is not recording.
- Q: Can the user switch **Uso del PC** in the middle of a transcription (e.g. leave the desk and want more CPU)? → A: Yes. Changing the control updates every job that is still queued or running. A job that has **not** started yet launches with the new thread budget. A job **already running** gets the new scheduling urgency immediately (so the OS can give it more or less CPU); its worker-thread count stays what it had at launch (raising threads mid-process would require restarting and losing progress). Quality preset remains snapshot-immutable.

### Session 2026-09-10

- Q: Keep **Dejar el PC usable** as the factory default? → A: No. The default for new configuration and new jobs is **Usar más CPU**. Configs saved under the old factory default migrate to **Usar más CPU** once; a later explicit choice of usable is kept. Mid-job thread count is still fixed at launch.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Choose how hard transcription hits the PC (Priority: P1)

As the primary user, I start a transcription (a finished meeting or an imported file) and I still need Teams, the browser, and the desktop to respond. I pick a setting that tells the app to leave the computer usable. I can still choose Equilibrado or Máxima calidad; that job will take longer, but other windows should not freeze.

**Why this priority**: This is the reported defect. Quality presets alone do not solve it.

**Independent Test**: With **Uso del PC** set to keep the computer usable, enqueue a transcription (any quality). Confirm the choice is visible, remembered after restart, and that the running job is constrained compared with the “use more CPU” choice (fewer worker threads / lower urgency; other apps remain the goal).

**Acceptance Scenarios**:

1. **Given** the sibling transcription tool is available, **When** the user looks at section 4, **Then** they see a **Uso del PC** choice next to the existing quality and language controls, with a short hint that quality and PC use are independent.
2. **Given** **Dejar el PC usable** is selected, **When** a new job is enqueued (record-and-transcribe or Transcribir archivo), **Then** that job stores the usable-PC choice and runs under that constraint even if the user later switches the control.
3. **Given** the user selected **Usar más CPU**, **When** a new job runs, **Then** that job is allowed to use the previous high-CPU behavior (almost all cores, still below a recording).
4. **Given** a choice was saved, **When** the user restarts the app, **Then** the same **Uso del PC** value is selected again.

---

### User Story 2 - Use the best model without abandoning the desktop (Priority: P2)

As the user, I would rather use Máxima calidad, but I switched to Equilibrado only because the machine locked up. I want to pick Máxima calidad **and** Dejar el PC usable, accepting a longer wait.

**Why this priority**: The user said they would use the best model if the PC stayed usable.

**Independent Test**: Select Máxima calidad + Dejar el PC usable, enqueue a short file, and confirm the job snapshot has both the max-quality mapping and the usable-PC constraint.

**Acceptance Scenarios**:

1. **Given** Máxima calidad and Dejar el PC usable are both selected, **When** a job is enqueued, **Then** the job uses the heavier recognition path **and** the usable-PC constraint.
2. **Given** Equilibrado and Dejar el PC usable, **When** a job runs, **Then** speaker labeling is still attempted (Equilibrado is unchanged as a quality choice); only how hard the PC is pushed changes.

---

### User Story 3 - Older jobs and recording still behave honestly (Priority: P3)

As the user, I understand that a job already in the queue keeps the PC-use choice it was given, that jobs created before this setting existed keep the old heavy-CPU behavior, and that starting a recording still pauses transcription completely.

**Why this priority**: Avoid surprising mid-queue changes; keep Recording Always Wins.

**Independent Test**: Enqueue under usable, switch the UI to “more CPU” before the job starts; the stored job stays usable. Load a job JSON without the new field; it behaves as the previous high-CPU path. Start recording during a job; transcription still suspends.

**Acceptance Scenarios**:

1. **Given** a pending job stored as usable, **When** the user changes **Uso del PC** in the UI, **Then** that pending job does not change.
2. **Given** a job file from before this feature (no PC-use field), **When** the worker runs it, **Then** it uses the previous high-CPU behavior.
3. **Given** a transcription is running, **When** the user starts recording, **Then** transcription still yields completely until recording ends (unchanged).

---

### Edge Cases

- Sibling tool missing: the new control is disabled like preset/language, with the same tooltip.
- Retry of a failed job: reuses the PC-use choice stored on that job, not the live combo.
- Very few CPU cores (2): usable still leaves at least one thread for the job; it must not request zero workers.
- User closes the app: the child process keeps the same constraint (env and priority were applied at launch).
- Out of scope: cloud offload, buying a GPU as a requirement, changing Equilibrado’s quality mapping, a numeric thread spinner, or a second transcription engine.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Recorder MUST expose a persisted **Uso del PC** choice with exactly two values: **Dejar el PC usable** and **Usar más CPU (más rápido)**.
- **FR-002**: Quality presets (Rápido / Equilibrado / Máxima calidad) MUST remain independent of **Uso del PC**. Any pairing MUST be valid.
- **FR-003**: The default for new configuration and new jobs MUST be **Usar más CPU**. Configs that only had the previous factory default MUST migrate to **Usar más CPU** once; an explicit later choice of **Dejar el PC usable** MUST persist.
- **FR-004**: When a job is enqueued, the job MUST store the PC-use choice in effect at enqueue time. Changing **Uso del PC** later MUST retarget queued and running jobs (not finished ones). Quality preset/model/speakers stay the snapshot from enqueue.
- **FR-005**: A job running as **Dejar el PC usable** MUST reserve CPU for other applications: fewer worker threads than the previous “almost all cores” path, and lower scheduling urgency than that path.
- **FR-006**: A job running as **Usar más CPU** MUST keep the previous high-CPU behavior (almost all cores minus a small reserve; still below an active recording).
- **FR-007**: Jobs loaded without a stored PC-use field MUST run as **Usar más CPU** (legacy).
- **FR-008**: Retry MUST honor the PC-use choice stored on that job.
- **FR-009**: Speaker labeling and recognition quality MUST still follow the job’s quality preset; **Uso del PC** MUST NOT silently turn off speakers or downgrade the model.
- **FR-010**: All processing MUST stay on the user’s machine (sibling subprocess + durable queue). Recording Always Wins MUST still suspend transcription during capture.
- **FR-011**: The UI MUST explain in plain language that Máxima calidad can be combined with a usable PC, and that the usable option makes transcription slower.
- **FR-012**: The same PC-use choice MUST apply to meeting jobs and imported-file jobs.
- **FR-013**: If the user changes **Uso del PC** while a transcription is queued or running, the app MUST apply that choice without asking them to cancel. Pending jobs MUST use the new thread budget at launch. An already-started process MUST get the new scheduling urgency within a few seconds; it MUST NOT be killed or restarted just to change thread count.

### Key Entities

- **PC-use choice**: Named user preference (`usable` | `full`) captured at enqueue; drives how hard a job may push the computer.
- **Transcription job**: Gains a stored PC-use choice alongside the existing quality snapshot (preset/model/beam/speakers).
- **User configuration**: Persists the last **Uso del PC** selection across restarts.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can find **Uso del PC**, change it, and confirm it is remembered after restart in under 30 seconds (no file editing).
- **SC-002**: On the same machine, a usable-PC job is launched with a strictly smaller thread budget than a more-CPU job when the machine has more than 4 logical processors (and never with more threads than the more-CPU path).
- **SC-003**: 100% of newly enqueued jobs after this feature include an explicit PC-use snapshot.
- **SC-004**: Selecting Máxima calidad together with Dejar el PC usable is possible in one screen, without changing files in the sibling project.
- **SC-005**: Starting a recording still fully pauses an in-flight transcription (no regression of Recording Always Wins).

## Assumptions

- The freeze is mainly CPU saturation (recognition + speaker labeling using nearly all cores, including libraries that ignored the existing thread flag) and scheduling, not a separate GPU requirement.
- A longer wall-clock time is acceptable if the desktop stays usable; the user already accepted Equilibrado for that reason.
- Two named choices beat a raw thread count for a single power user.
- Work WAVs, queue, and logs stay in local app data; this feature does not change output folders.
