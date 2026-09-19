# Feature Specification: Selected Recordings Folder for Conversion Outputs

**Feature Branch**: `010-selected-folder-outputs`

**Created**: 2026-08-20

**Status**: Draft

**Input**: User description: "Cuando se cambia la carpeta de las grabaciones, esta haciendo las conversiones en otro lado, no esta tomando esa carpeta seleccionada, deberia ser la misma que se ha seleccionado"

## Clarifications

### Session 2026-08-20

Decisions encoded from the user request, constitution (paths robust; recording wins), and existing product behavior. Not blocked on interactive Q&A.

- Q: After the user changes **Carpeta de salida**, where must meeting artifacts go? → A: The selected folder is the source of truth. The MP4 of a meeting recorded after the change, and that meeting’s user-visible conversion/transcription folder, MUST live under that selected folder (not the previous folder, not the product default, not the sibling transcription project).
- Q: Should imported files (Transcribir archivo / drop) copy results into the selected recordings folder? → A: No. The complaint is about changing the recordings folder. Imported media keeps results next to the source file (`Transcripciones/<stem>/` beside the original). Meetings recorded into the selected folder are the in-scope path.
  **Superseded 2026-09-09 by spec 014**: imported *transcripts* (not a copy of the media) go under Carpeta de salida. The original file is still not copied.
- Q: May internal work files (queue, logs, temporary extracted audio) stay outside the selected folder? → A: Yes. Those remain in unsynced local app data so OneDrive does not corrupt them. The user must not have to browse there to find the meeting video or the readable transcript.
- Q: When does a newly picked folder take effect? → A: Immediately for the next meeting start (and it must be remembered across restarts). Jobs already queued for a file that still lives in an older folder keep writing that meeting’s transcript beside that existing file.
- Q: Must prior meetings be moved when the folder changes? → A: No. Already-saved videos stay where they were. Only new meetings (and their conversions) follow the new folder.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - New meetings follow the folder just chosen (Priority: P1)

As the primary user, I change **Carpeta de salida** to a different directory (for example a project folder, an external drive, or a path that is not the default Videos/Grabaciones). I then record a meeting (with transcribe-on-finish on or off). I expect the saved recording **and** the conversion/transcription results I later open to be inside that chosen folder—not in the previous location, not in the app’s default recordings folder, and not inside the sibling transcription tool’s own output directory.

**Why this priority**: This is the reported defect. Changing the folder is useless if conversions still land “somewhere else.”

**Independent Test**: With a known previous/default recordings folder, pick a distinct empty folder as Carpeta de salida, record a short meeting with transcribe-on-finish enabled, and confirm both the video and the transcript folder appear under the newly selected folder.

**Acceptance Scenarios**:

1. **Given** the app currently points at folder A (or the factory default), **When** the user chooses folder B as Carpeta de salida and records a meeting, **Then** the finished video is stored in B (not A, not the default recordings location).
2. **Given** transcribe-on-finish is enabled and the sibling transcription tool is available, **When** that meeting is converted/transcribed, **Then** the user-visible transcript folder for that meeting is under B (same selected recordings folder), in the usual `Transcripciones/<recording-name>/` layout.
3. **Given** the user chose B and has not started a recording yet, **When** they close and reopen the app, **Then** Carpeta de salida still shows B and the next meeting still uses B.

---

### User Story 2 - “Abrir” and browsing match the selected meeting folder (Priority: P2)

As the user, after a meeting saved into the folder I just selected, I use in-app actions that open folders (open recordings folder, open transcript) and I land on that same selected tree—not on a leftover default path.

**Why this priority**: The original complaint is that conversions happen “somewhere else”; opening the wrong directory is how that bug is discovered.

**Independent Test**: After story 1, use the in-app open-folder / open-transcript actions and confirm Explorer shows paths under the selected folder B.

**Acceptance Scenarios**:

1. **Given** a meeting just saved into B, **When** the user opens the recordings folder from the result of that meeting, **Then** Explorer shows B (or the file inside B), not folder A.
2. **Given** that meeting’s transcript finished, **When** the user opens the transcript location, **Then** they see the transcript files under B’s `Transcripciones` tree.

---

### User Story 3 - Older files and imports stay honest (Priority: P3)

As the user, I understand that changing Carpeta de salida does not relocate old meetings. **Superseded in part by 014**: transcribing a file that already lives elsewhere now writes user-visible transcripts under Carpeta de salida; the original is still not copied.

**Why this priority**: Prevents “helpfully” moving or duplicating archives; 014 later redirected import *transcripts* only.

**Independent Test**: Leave an old meeting in folder A; change to B; transcribe the old file (or an import from another disk). Confirm A’s media is not copied into B; new meetings still go to B; transcripts of that import appear under B (014).

**Acceptance Scenarios**:

1. **Given** a finished video still in folder A, **When** the user switches Carpeta de salida to B and transcribes that existing A file, **Then** the original is not copied into B; user-visible transcript output follows Carpeta de salida B (014).
2. **Given** the user imports a podcast from a folder that is not B, **When** transcription finishes, **Then** results are under B (014), not forced beside the podcast file.
3. **Given** a transcription job was already queued for a file in A before the folder change, **When** that job runs, **Then** it still writes that job’s user-visible results to the destination snapshotted at enqueue, while the next *new* recording uses B.

---

### Edge Cases

- Selected folder is on another drive, a path with spaces, or a OneDrive-synced directory: the video and readable transcripts still go there; only internal queue/logs/temp extraction stay off sync.
- Selected folder cannot be created or written (permissions, missing drive): the user gets a clear failure; files MUST NOT silently fall back to the old default folder.
- User changes folder while a recording is already in progress: the meeting that is already capturing keeps its original destination; the new folder applies to the next recording.
- User changes folder while a conversion of an older file is running: that in-flight job does not get redirected mid-write.
- Empty or unchanged picker (user cancels the folder dialog): previous selection remains.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The directory shown as Carpeta de salida MUST be the destination for the next meeting’s saved video.
- **FR-002**: User-visible conversion and transcription outputs for a meeting recorded into that directory MUST be stored under the same selected directory (standard `Transcripciones/<recording-name>/` layout), not under a previous recordings folder, not under the factory default recordings location, and not under the sibling transcription project’s private output tree.
- **FR-003**: Choosing a new Carpeta de salida MUST persist immediately as the remembered preference (survives app restart) without requiring the user to start a recording first.
- **FR-004**: Paths used for those user-visible meeting outputs MUST be complete (not relative to the app or to the sibling tool), so conversions cannot land inside the transcription project by accident.
- **FR-005**: Internal working files (durable queue, process logs, temporary extracted audio) MAY remain in unsynced local app data and MUST NOT be treated as the user-visible destination.
- **FR-006**: **Superseded by 014.** Imported *media* MUST NOT be copied into Carpeta de salida. User-visible *transcripts* of new imports MUST go under Carpeta de salida (`Transcripciones/<stem>/`).
- **FR-007**: Meetings already stored in a previous folder MUST stay there; changing Carpeta de salida MUST NOT relocate or re-convert past videos.
- **FR-008**: If the selected folder cannot be used, the app MUST fail visibly rather than writing the meeting or its transcripts to a fallback default location.
- **FR-009**: An in-progress recording MUST keep the output folder it started with; the newly selected folder applies to subsequent recordings.

### Key Entities

- **Selected recordings folder**: The directory the user chose as Carpeta de salida; source of truth for new meeting videos and those meetings’ visible transcripts.
- **Meeting video**: The finished recording the user browses and plays.
- **User-visible transcript folder**: The per-meeting folder of readable transcript files (`Transcripciones/<name>/`).
- **Internal work files**: Queue entries, logs, and temporary audio used only by the background conversion pipeline.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After changing Carpeta de salida to a new empty folder, 100% of a subsequent test meeting’s video and user-visible transcript files appear under that folder (zero files for that meeting in the previous recordings folder, the factory default, or the sibling tool’s output tree).
- **SC-002**: A user can change the folder and, without recording first, quit and reopen; the same folder is still selected and the next meeting uses it (preference round-trip on first try).
- **SC-003**: A tester following the primary flow (change folder → record short meeting → wait for conversion) can locate both the video and the transcript by browsing only the selected folder, in under one minute after conversion finishes.
- **SC-004**: Changing the folder does not move or duplicate an older meeting that remains in the previous location (zero unexpected copies into the new folder).

## Assumptions

- The user who reported the bug is the same single power user as the rest of the product; one remembered Carpeta de salida is enough (no per-project profiles).
- “Conversiones” in the report means the user-visible meeting pipeline after stop (final video plus transcription/conversion results they find in Explorer), not the hidden temporary audio used only by the worker.
- Feature 009 (transcribe any file) remains for picker/drop UX. Feature 014 redirects imported transcript *folders* to Carpeta de salida; the original media is still not copied.
- Work queues, logs, and temp extraction stay outside cloud-synced folders, as already required by the constitution.
- The sibling transcription engine remains a separate process; this feature does not merge environments or add cloud processing.
- Recording still has absolute CPU priority over conversion.
