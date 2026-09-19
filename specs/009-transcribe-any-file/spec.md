# Feature Specification: Transcribe Any Audio File

**Feature Branch**: `009-transcribe-any-file`

**Created**: 2026-08-17

**Status**: Draft

**Input**: User description: "Ayudame que dentro de la app, pueda transcribir el audio de cualquier cosa, no solo de las reuniones que se tengan, que la interfaz me de esa opcion, investiga bien como se deberia tener esto, buenas practica de ux y demas."

## Clarifications

### Session 2026-08-17

Decisions encoded from the user request, existing Recorder patterns, and desktop transcription UX (picker + drop, one queue, source file stays put). Not blocked on interactive Q&A.

- Q: Where should transcript results for an imported file live? → A: Next to the source file, in a Transcripciones folder named from the file stem (same layout as meeting recordings). Do not copy the original into Grabaciones.
  **Superseded 2026-09-09 by spec 014**: new imports write user-visible transcripts under Carpeta de salida (`Transcripciones/<stem>/`). The original file still is not copied.
- Q: What happens if the user imports a path that already finished successfully? → A: Do not start a duplicate job; tell the user a transcript already exists and let them open it.
- Q: How should import errors be shown so recording is not disrupted? → A: In-window, non-modal message (status/banner). The file picker itself may be modal because the user invoked it. No error dialog that must be dismissed before capture can continue.
- Q: Can one action enqueue several files? → A: Yes — enqueue every supported file; skip and report unsupported items; the existing sequential worker processes them one at a time.
- Q: Must the original media be copied off cloud-synced drives before work starts? → A: No copy of the original. Extracted working audio and the durable queue stay outside synced folders, as they already do for meetings.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Transcribe an existing file from the main window (Priority: P1)

As the primary user, I want a visible action in the Recorder to transcribe an audio or video file I already have (podcast, call export, lecture, previous recording, etc.) so I do not have to record a meeting first or leave the app to use the sibling transcription tool by hand.

**Why this priority**: Today transcription is only offered as “transcribe when this recording finishes.” The user cannot ingest arbitrary media from the UI. Local-file import is a first-class action in comparable desktop transcription products (picker + drop onto the window; same settings as other jobs).

**Independent Test**: With the sibling tool available, choose a supported audio/video file from the main window, confirm it appears in the existing transcription status UI, and when it finishes, open the same kind of transcript artifacts as a meeting job.

**Acceptance Scenarios**:

1. **Given** the app is idle and the sibling transcription tool is available, **When** the user chooses **Transcribir archivo…** and picks a supported file, **Then** a job is added to the existing durable queue using the currently selected speed/quality preset and language, the status banner shows that job, and the original file is left in place.
2. **Given** preset and language are set (e.g. Rápido / English), **When** the user transcribes a file, **Then** that job uses those choices (snapshot at enqueue); later UI changes do not rewrite that job.
3. **Given** the sibling tool is unavailable, **When** the user looks at transcription controls, **Then** **Transcribir archivo…** is disabled or clearly unavailable with the same class of guidance as “Transcribir al terminar.”
4. **Given** a recording is in progress, **When** the user transcribes a file, **Then** the file is accepted into the queue without stopping the recording, and background transcription still yields to capture (does not start or stays paused until recording ends).

---

### User Story 2 - Drop files onto the window (Priority: P2)

As the user, I want to drag supported audio/video files from Explorer onto the Recorder window so importing is as fast as picking from a dialog, matching desktop conventions.

**Why this priority**: Drag-and-drop is the expected companion to a file picker in desktop transcribers; it is not required for an MVP but is the natural second path once the picker exists. It also lets the user enqueue during a recording without opening a modal dialog.

**Independent Test**: Drag one or more supported files onto the window; they enqueue like picker imports. Drag an unsupported item; the user gets a clear message and the queue is not polluted.

**Acceptance Scenarios**:

1. **Given** the sibling tool is available, **When** the user drops one or more supported files onto the window, **Then** each valid file is enqueued like a picker import, using the current preset and language.
2. **Given** a file is dropped that is not a supported audio/video type (or is a folder), **When** the drop is processed, **Then** the user sees a clear error, no job is created for that item, and other valid files in the same drop still enqueue.
3. **Given** a recording is in progress, **When** the user drops a supported file, **Then** enqueue is allowed (queue-only); capture is not interrupted.
4. **Given** the sibling tool is unavailable, **When** the user drops a file, **Then** the drop is refused with the same class of guidance as a disabled picker action.

---

### User Story 3 - Understand import vs recording, and recover from errors (Priority: P2)

As the user, I want the interface to separate “record a meeting” from “transcribe something I already have,” and to explain failures (unsupported type, missing file, already transcribed, missing tool) without freezing the window.

**Why this priority**: Without this, users may think they must hit Record first. Clear empty/error states are table stakes for a first-class import action.

**Independent Test**: With Transcriptor missing, with an unsupported file, and with a file already successfully transcribed, confirm messages are visible and the rest of the app (including recording) stays usable.

**Acceptance Scenarios**:

1. **Given** the main window, **When** the user scans the transcription area, **Then** they can distinguish auto-transcribe-after-recording from transcribe-an-existing-file without opening a hidden menu.
2. **Given** the user picks or drops an unsupported file, **When** validation runs, **Then** they see a non-blocking message naming the problem; recording and other queue jobs continue.
3. **Given** that file was already transcribed successfully (same path still treated as done), **When** the user imports it again, **Then** they are told a transcript already exists and can open it instead of silently doing nothing or starting a duplicate hours-long job.
4. **Given** a job fails because the source file vanished or has no usable audio, **When** the status UI updates, **Then** the failure is visible with Retry / View log / Clear failed as they work today for meeting jobs.

---

### Edge Cases

- Multiple files in one picker/drop: enqueue every supported file; report skipped ones; process remains one-at-a-time via the existing queue.
- File already pending/running: do not enqueue a duplicate; tell the user it is already in the queue.
- File already done: do not start a second job; offer to open the existing transcript.
- File previously failed/cancelled: allow enqueue/retry using existing queue rules (failed entries can be retried or cleared).
- Recording in progress: import remains available; transcription work yields to capture.
- Closing the banner does not cancel the imported job (same as meeting jobs).
- Source on a disconnected drive or deleted after enqueue: job fails with a clear “file no longer exists” style message; the original is never moved by the app.
- Very long names / characters unsafe for result folders: the visible job name stays recognizable from the source file’s name; result artifacts remain openable from the status UI.
- Multi-track meeting recordings imported this way MUST still transcribe the full mix (not a single “system only” track). Arbitrary single-track files use their only audio.
- Cloud-synced source files that are not fully local may fail extraction; the user sees a failure they can retry after the file is available locally. Working copies of extracted audio still live outside synced folders.
- Out of scope: cloud upload, LLM/minutas, a second transcription engine, a full history dashboard, editing an already-queued job’s preset/language, transcribing a live URL/stream, or batch folder recursion.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The main window MUST offer a first-class **Transcribir archivo…** action (not only a hidden menu) that opens a file picker of common audio and video types the product can transcribe.
- **FR-002**: The same action MUST be visually grouped with existing transcription settings (preset and language) and clearly distinct from **Grabar** and from **Transcribir al terminar**.
- **FR-003**: Choosing one or more supported files MUST enqueue them on the **existing** durable transcription queue (no parallel queue or separate status surface).
- **FR-004**: Imported jobs MUST use the preset and language in effect at enqueue time, with the same snapshot immutability as meeting jobs.
- **FR-005**: The original media file MUST remain in its original location (the app does not move or require copying it into the recordings folder).
- **FR-006**: Transcript results for an imported file MUST be as discoverable as meeting transcripts: openable from the existing **Abrir** control. **Superseded by 014**: stored under Carpeta de salida in `Transcripciones/<stem>/`, not next to the source file. The original media stays in place (FR-005).
- **FR-007**: The window MUST accept drag-and-drop of supported files as an equivalent enqueue path to the picker.
- **FR-008**: Unsupported types, folders, and missing sibling tool MUST produce a clear in-window, non-modal message (status or banner). They MUST NOT freeze the UI, MUST NOT require dismissing a dialog before recording can continue, and MUST NOT interrupt capture. The file picker may be modal only because the user opened it.
- **FR-009**: Import MUST be allowed while a recording is active; background transcription MUST still yield to recording (Recording Always Wins).
- **FR-010**: Re-import of a path that already has an active or successful job MUST NOT duplicate work; the user MUST be informed and, if done, able to open the existing result.
- **FR-011**: Cancel, retry, clear failed, view log, and open transcript MUST work for imported jobs exactly as for meeting jobs.
- **FR-012**: All processing remains local; no cloud upload; no LLM/minuta generation.
- **FR-013**: Supported types MUST include at least: mp3, m4a, wav, flac, ogg, opus, aac, wma, mp4, m4b, mkv, webm, mov, avi (the set the sibling tool already accepts).
- **FR-014**: When extracting audio from a Recorder multi-track meeting file, the product MUST transcribe the mixed meeting audio, not a single isolated track.
- **FR-015**: This feature MUST NOT introduce a full queue-history dashboard or a dedicated second window as the primary flow.

### Key Entities

- **Imported media file**: A user-owned audio or video file that already exists on disk; remains the source of truth on disk; referenced by a durable job.
- **Transcription job**: Same durable queue unit as meeting transcription (status, preset, language, result location, log). Gains an origin that may be “imported file” vs “finished recording” only insofar as the UI/queue already need to show a file name.
- **Transcription status UI**: Existing banner (progress, cancel, retry, open, log, clear failed) reused for imported jobs.
- **User configuration**: Existing persisted preset, language, and transcribe-after-recording; no new preference required for MVP besides using those settings on import.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From a ready main window, a user who has never recorded in this session can start transcribing a local file in under 30 seconds (one visible action + file choice), without using a terminal or editing config files.
- **SC-002**: 100% of imported jobs appear in the same status UI as meeting jobs, with cancel/open/retry available in the same states as today.
- **SC-003**: 100% of newly imported jobs snapshot the preset and language selected at enqueue time.
- **SC-004**: Dropping or picking an unsupported file never blocks recording or the rest of the UI; the user sees a message in under 5 seconds.
- **SC-005**: Import during an active recording never stops or pauses capture in manual checks; the imported job waits or stays paused until recording yields.
- **SC-006**: After a successful import job, the user can open the transcript from the status UI in one click; the original media file is still at its original path.
- **SC-007**: A user can distinguish “transcribe this recording when it ends” from “transcribe a file I already have” on first glance at the transcription area (no hunting in menus).

## Assumptions

- Single primary user; one transcription worker processing jobs sequentially remains the product model.
- Extending the existing transcription panel/queue is better UX than a new window (desktop recorders keep import next to existing transcribe settings; a second window would hide progress and duplicate preset/language).
- **Transcribir archivo…** is a button in the current output/transcription group, with a short hint that preset and language apply to both recordings and imported files; drag-and-drop is a first-class companion, not a hidden extra.
- Original files stay in place (do not copy into Grabaciones): avoids duplicating large videos and mixing personal media with meeting recordings. User-visible transcripts of new imports follow Carpeta de salida (`…/Transcripciones/<nombre>/`); see spec 014.
- Job display name is the source file’s name (sanitized only as needed for result folders), analogous to how meeting files are named from the window title.
- Working extracted audio and the durable queue continue to live outside cloud-synced folders, as they do for meetings.
- File picker filters match the sibling tool’s accepted audio/video types; validation is by type/extension (and “no usable audio” at processing time).
- Multiple files in one action are in scope (enqueue all valid); recursive folder import is not.
- If a path is already done, informing + Open is better than silent no-op (today’s post-recording enqueue can silently skip duplicates).
- Modal file picker during recording is acceptable; drop-on-window is the non-modal alternative. Neither may start heavy transcription CPU until recording yields.
- No constitution change: recording still wins; transcription stays a sibling subprocess; privacy stays local; no LLM.
- Evidence for UX: desktop transcription apps treat import as picker + full-window drop, reuse one settings/queue surface, keep the source file, and show a drop overlay rather than a buried menu item.
