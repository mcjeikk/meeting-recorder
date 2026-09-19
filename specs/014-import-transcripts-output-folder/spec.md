# Feature Specification: Imported Transcripts Follow Carpeta de Salida

**Feature Branch**: `014-import-transcripts-output-folder`

**Created**: 2026-09-09

**Status**: Draft

**Input**: User description: "asi le ponga una ruta de salida para las grabaciones las esta poniendo donde le estoy importando las grabaciones, eso se debe arreglar"

## Clarifications

### Session 2026-09-09

Decisions encoded from the user report and existing Recorder patterns (snapshot at enqueue, original file stays put, work files in local app data). Not blocked on interactive Q&A.

- Q: Where must user-visible transcripts of an imported file go? → A: Under the currently selected **Carpeta de salida**, in the same `Transcripciones/<file-stem>/` layout as meeting recordings. Not next to the imported file.
- Q: Must the original imported media be copied or moved into Carpeta de salida? → A: No. The original stays where the user imported it from. Only readable transcript artifacts go to Carpeta de salida.
- Q: If Carpeta de salida changes while a job is already queued or running? → A: That job keeps the destination snapshotted at enqueue. The new folder applies to later imports and later recordings.
- Q: What about jobs already queued without a destination snapshot (legacy)? → A: They keep writing beside the source file so in-flight work is not redirected mid-write.
- Q: Does this change meeting recordings? → A: No. New meetings still save the video into Carpeta de salida and their transcripts under that same folder. This feature only redirects **imported** transcriptions that were incorrectly landing next to the source.

**Supersedes**: spec 009 FR-006 (transcripts next to the imported source) and spec 010 FR-006 / US3 acceptance that imports stay source-adjacent. Meeting-folder behavior from 010 remains.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Imported transcripts land in Carpeta de salida (Priority: P1)

As the primary user, I choose a recordings folder (Carpeta de salida) and then transcribe existing files with **Transcribir archivo…** or by dropping them on the window. I expect the readable transcripts in that same chosen folder—not a `Transcripciones` folder next to the files I imported (Downloads, a USB drive, an interview dump, etc.).

**Why this priority**: This is the reported defect. Setting Carpeta de salida is useless for imports if conversions still appear beside the source.

**Independent Test**: Set Carpeta de salida to an empty folder B. Import a supported file that lives in a different folder A. When the job finishes, transcript files exist under B and not under A (the original media is still in A).

**Acceptance Scenarios**:

1. **Given** Carpeta de salida is folder B and a supported file lives in folder A (A ≠ B), **When** the user imports that file, **Then** user-visible transcript output is under B’s `Transcripciones/<file-stem>/` tree, not under A.
2. **Given** the same import, **When** transcription finishes, **Then** the original file is still at its original path in A (not copied or moved into B).
3. **Given** Carpeta de salida is B, **When** the user opens the finished imported transcript from the app, **Then** they land under B, not next to the source in A.

---

### User Story 2 - Meetings and in-flight jobs stay honest (Priority: P2)

As the user, I still find new meeting videos and their transcripts under Carpeta de salida. Changing the folder does not yank an already-queued import to a new place, and old transcripts already written next to a source file are not relocated.

**Why this priority**: Prevents breaking 010’s meeting path and avoids corrupting a job that is already writing.

**Independent Test**: Record a short meeting into B (transcripts still under B). Queue an import, then change Carpeta de salida to C before that import runs; that import still finishes in B. A previously written source-adjacent transcript is left in place.

**Acceptance Scenarios**:

1. **Given** Carpeta de salida is B, **When** the user records a meeting, **Then** the video and that meeting’s transcripts remain under B (unchanged from selected-folder behavior).
2. **Given** an imported job was queued while Carpeta de salida was B, **When** the user then changes Carpeta de salida to C before that job runs, **Then** that job’s user-visible results still go under B.
3. **Given** a transcript already exists next to an old source file from before this change, **When** Carpeta de salida is B, **Then** the app does not move or delete that old transcript folder as a side effect of the folder preference.

---

### User Story 3 - Abrir and empty hints match the selected folder (Priority: P3)

As the user, the interface does not tell me transcripts of imported files will appear beside the source. After import, **Abrir** matches Carpeta de salida.

**Why this priority**: The confusion was “I set an output path and results appeared where I imported from.” Copy in the UI must not contradict the new destination.

**Independent Test**: Read the import hint; import one file; use Abrir; Explorer shows the selected recordings tree.

**Acceptance Scenarios**:

1. **Given** the main window, **When** the user reads the transcribe-file hint, **Then** it does not claim results are stored next to the imported file.
2. **Given** a finished imported job, **When** the user clicks **Abrir**, **Then** the opened location is under Carpeta de salida.

---

### Edge Cases

- Carpeta de salida on another drive, a path with spaces, or a synced folder: user-visible transcripts still go there; working WAV/queue/logs stay in unsynced local app data.
- Selected folder not writable: fail visibly; do not silently write next to the source or to the factory default recordings folder.
- Two imported files with the same stem (same name, different folders): they share the same result folder name under Carpeta de salida; later success may overwrite that stem’s transcript tree. Dedupe of *the same path* still prevents a second job.
- Re-import of a path already marked done: still do not start a duplicate; **Abrir** uses the stored result location (which may be the new folder or a legacy source-adjacent path).
- Legacy queued job with no destination snapshot: writes beside the source (old rule) rather than jumping to the current Carpeta de salida.
- Original on a disconnected drive after enqueue: extraction fails with a clear message; no copy of the original was required.
- Out of scope: moving old transcripts into the new folder, copying imported media into Grabaciones, a second output picker just for transcripts, cloud upload, LLM.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: User-visible transcript artifacts for a newly imported file MUST be stored under the Carpeta de salida in effect at enqueue time, in the standard `Transcripciones/<source-stem>/` layout.
- **FR-002**: The imported original media file MUST remain at its original path (no copy or move into Carpeta de salida).
- **FR-003**: The destination for an imported job MUST be captured when the job is queued so a later change of Carpeta de salida does not redirect that job.
- **FR-004**: Newly recorded meetings MUST keep saving video and transcripts under Carpeta de salida (behavior from the selected-folder feature is unchanged).
- **FR-005**: Jobs that have no captured destination (queued before this change) MUST keep the previous source-adjacent transcript location.
- **FR-006**: **Abrir** for an imported job MUST open the captured/result location (under Carpeta de salida for new imports), not invent a folder next to the source.
- **FR-007**: Internal working files (queue, logs, temporary extracted audio) MUST remain in unsynced local app data and MUST NOT be treated as the user-visible destination.
- **FR-008**: If Carpeta de salida cannot be used for those user-visible transcripts, the job MUST fail visibly rather than writing beside the imported file or to a factory default folder.
- **FR-009**: In-window copy about **Transcribir archivo…** MUST NOT tell the user that results are stored next to the imported file.

### Key Entities

- **Selected recordings folder (Carpeta de salida)**: Destination for new meeting videos and for user-visible transcripts of newly imported files.
- **Imported media file**: User-owned audio or video that stays on disk at its original path; referenced by the durable job.
- **Job destination snapshot**: The recordings folder remembered on the job at enqueue; used when writing and when opening results.
- **User-visible transcript folder**: `Transcripciones/<stem>/` under that destination (txt/srt/json the user browses).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After setting Carpeta de salida to a folder B distinct from the import source folder A, 100% of a subsequent imported test file’s user-visible transcript files appear under B and 0% appear as a new `Transcripciones` tree under A.
- **SC-002**: After that import, the original media file is still at its original path (zero copies of the media into B).
- **SC-003**: A tester following the primary flow (set folder B → import a file from A → wait for conversion) can locate the transcript by browsing only B, in under one minute after conversion finishes.
- **SC-004**: Changing Carpeta de salida after an import is already queued does not move that job’s output (the queued job still finishes in the folder captured at enqueue).

## Assumptions

- The user who reported the bug is the same single power user; one Carpeta de salida is enough (no separate “transcripts folder” preference).
- “Poniéndolas donde le estoy importando” means the user-visible `Transcripciones/<stem>/` tree beside the source, not the hidden work WAV in local app data.
- Meeting recordings already follow Carpeta de salida because the video is written there first; this feature does not retarget mux.
- Layout stays `Transcripciones/<stem>/` so Explorer and **Abrir** stay familiar.
- Work queues, logs, and temp extraction stay outside cloud-synced folders (constitution).
- Transcription remains a sibling subprocess; `--output` stays an absolute path so results never land inside the Transcriptor project.
- Specs 009 (import UX, no copy of original) and 010 (meetings follow the selected folder) remain except where this spec explicitly supersedes import result location.
