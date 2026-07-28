# Feature Specification: Transcription Queue Controls

**Feature Branch**: `003-transcription-queue-controls`

**Created**: 2026-07-27

**Status**: Draft

**Input**: User description: "UX/controls for the transcription queue from Recorder: cancel active or pending jobs from the UI, choose transcription language in the UI (today only in config), and clear failed jobs — focused MVP extending the existing banner/retry/log controls without a full history dashboard."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Cancel a queued or running transcription (Priority: P1)

As the primary user, I want to cancel a pending or in-progress transcription from the Recorder so that I can free CPU when I no longer need that transcript (wrong meeting, wrong preset, or I need the machine free).

**Why this priority**: Today the banner shows progress and allows retry after failure, but there is no way to stop work once enqueued. Long jobs (~2× audio duration) make cancel the highest-value control gap.

**Independent Test**: Enqueue a transcription (or start one), click Cancel while pending or running, and confirm the job stops, the UI reports cancellation, and no further CPU work continues for that job.

**Acceptance Scenarios**:

1. **Given** a job is pending (not yet started), **When** the user cancels it, **Then** it does not start, the UI shows it was cancelled, and it is no longer treated as active work.
2. **Given** a job is extracting or running, **When** the user cancels it, **Then** background processing for that job stops within a short time, the UI shows cancellation, and recording (if any) is unaffected.
3. **Given** a job is already done or already failed, **When** the user looks at the banner, **Then** Cancel is not offered as the primary action for that finished state (Retry/Open remain as today where applicable).

---

### User Story 2 - Choose transcription language in the UI (Priority: P1)

As the user, I want to pick the transcription language (or auto-detect) in the Recorder before a job is enqueued so I do not have to edit config files.

**Why this priority**: Language already exists in persisted configuration and is passed to the sibling tool, but it is invisible in the UI — a common desktop expectation and a frequent need for mixed-language meetings.

**Independent Test**: Change the language control, restart the app (selection restored), enqueue a job, and confirm the job carries the selected language.

**Acceptance Scenarios**:

1. **Given** the app is idle, **When** the user selects Spanish, English, or Auto, **Then** the choice is visible and saved for the next launch.
2. **Given** a language is selected, **When** a recording finishes with auto-transcribe on, **Then** the new job uses that language (snapshot at enqueue; later UI changes do not rewrite an already-queued job’s language).
3. **Given** the sibling tool is unavailable, **When** the user views transcription controls, **Then** language selection remains visible or clearly disabled with the same class of guidance as other transcription controls.

---

### User Story 3 - Clear failed (and cancelled) jobs from the queue (Priority: P2)

As the user, I want to remove failed or cancelled queue entries I no longer care about so the durable queue does not accumulate clutter and Retry is not confused with stale failures.

**Why this priority**: Useful hygiene after cancel/errors; less urgent than stop-the-job and language, but small and high clarity.

**Independent Test**: With one or more failed/cancelled jobs present, use Clear failed; confirm those entries are gone from the queue store and the banner no longer implies they are actionable failures (unless a new job appears).

**Acceptance Scenarios**:

1. **Given** one or more jobs in failed or cancelled state, **When** the user clears failed jobs, **Then** those queue entries are removed and successful/pending/running jobs are left alone.
2. **Given** no failed or cancelled jobs, **When** the user would clear, **Then** the action is unavailable or clearly does nothing harmful.
3. **Given** a job is pending or running, **When** the user clears failed jobs, **Then** that active work is not cancelled or deleted by the clear action.

---

### Edge Cases

- What if cancel is pressed twice quickly? Second cancel is a no-op; UI stays consistent.
- What if the worker process already exited when cancel arrives? Job is marked cancelled/failed-settled without crashing the app.
- What if another Recorder instance owns the worker lock? Cancel still updates the durable queue so the owning worker honors cancel on its next check (or best-effort terminate if this instance owns the process).
- What if the user starts recording during cancel? Recording Always Wins; cancel must not block or degrade capture.
- What if language is unknown/corrupt in config? Fall back to Spanish (`es`), matching today’s product default.
- Closing the banner (✕) does not cancel the job; only the explicit Cancel action does.
- Out of scope for this MVP: full multi-job history panel, reordering the queue, editing language/preset of an already-queued job, hotplug device refresh, model-daemon Phase 2 from feature 002.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Recorder MUST let the user cancel the current pending or active transcription job from the main transcription status UI.
- **FR-002**: Cancelling a running job MUST stop sibling transcription work for that job (best-effort process stop) and MUST NOT interrupt an active recording.
- **FR-003**: Cancelled jobs MUST be distinguishable from successful completion and from generic processing errors in the status UI.
- **FR-004**: The Recorder MUST expose a language control with at least: Spanish (`es`), English (`en`), and Auto-detect (`auto`).
- **FR-005**: The selected language MUST persist in user configuration and restore on launch.
- **FR-006**: Newly enqueued jobs MUST store the language in effect at enqueue time; later UI changes MUST NOT mutate that job’s language.
- **FR-007**: The Recorder MUST provide an action to clear failed and cancelled jobs from the durable queue without removing pending, running, or successfully completed jobs that the product still treats as done records (done records MAY remain unless the product already overwrites/dedupes by media path as today).
- **FR-008**: Existing Retry (on error), Open transcript (on done), and View log (on error) behaviors MUST remain available where they apply today.
- **FR-009**: Queue control actions MUST respect Recording Always Wins and MUST keep transcription as a sibling subprocess integration.
- **FR-010**: All processing remains local; no cloud upload of meeting media.
- **FR-011**: This feature MUST NOT introduce a full queue-history dashboard in the MVP.

### Key Entities

- **Transcription Job**: Durable queue unit; gains a cancellable lifecycle (pending/active → cancelled) and already carries language + preset snapshot.
- **User Configuration**: Persisted preferences including `transcription_language` and existing transcription toggles/presets.
- **Transcription Status UI**: Banner/controls showing progress, cancel, retry, open, log, and clear-failed for the current/relevant job context.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From a visible pending or running job, the user can cancel it in under 10 seconds of interaction and see a cancelled state without editing files.
- **SC-002**: After cancel of a running job, no further meaningful transcription CPU work continues for that job within ~15 seconds on a typical machine (process gone or idle).
- **SC-003**: A user can change language in the UI and confirm it survives restart in under 30 seconds (no config-file editing).
- **SC-004**: 100% of newly enqueued jobs after this feature carry the language selected at enqueue time.
- **SC-005**: Clear failed removes only failed/cancelled entries; pending/running jobs continue unaffected in 100% of manual checks in quickstart.
- **SC-006**: Starting or continuing a recording during cancel/clear still prioritizes capture (no regression vs. current Recording Always Wins behavior).

## Assumptions

- Single primary user; one active transcription job at a time remains the product model (worker already processes sequentially).
- Language codes `es`, `en`, and `auto` match what the sibling CLI already accepts via `--language`.
- “Clear failed” deletes durable queue files for error/cancelled statuses; done jobs may remain for dedupe-by-media as today.
- Cancel of a job owned by another app instance is best-effort via durable status; perfect cross-instance kill is not required for MVP.
- Full history UI, mid-queue edit, and hotplug are deferred (candidate later features).
- Evidence for this feature is primarily codebase audit + common desktop queue UX patterns; no performance claims beyond “stop work after cancel.”
