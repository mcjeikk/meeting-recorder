# Feature Specification: Never Delete an Unsaved Recording

**Feature Branch**: `017-never-delete-unsaved-recording`

**Created**: 2026-09-09

**Status**: Implemented

**Input**: User: this must never happen again. The app must not delete temporary recording files if an output path is not defined. If the path is missing or invalid, it must ask the user to correct it. A failed save must not destroy the capture.

## User Scenarios & Testing

### User Story 1 - A failed save still leaves the recording (Priority: P1)

The user stops a recording. Combining video and audio, or writing the final file, fails (folder missing, too long for Windows, no permission, encoder error, OneDrive placeholder). The capture files remain on the machine. The user is told the recording was not discarded and is asked to pick a usable folder. After they choose one, the finished file appears there.

**Why this priority**: On 2026-09-09 an interview was captured and then destroyed because save failed and the session folder was deleted anyway. That loss is irrecoverable.

**Independent Test**: Force a save to an unusable folder after a capture exists; the session files are still present; choosing a short valid folder produces the finished movie.

**Acceptance Scenarios**:

1. **Given** a capture that has been stopped, **When** writing the finished file to the chosen folder fails, **Then** the working capture files are still on disk and the user sees that nothing was thrown away.
2. **Given** that failed save, **When** the user picks a valid folder, **Then** the finished recording is stored there and only then may the working files be removed.
3. **Given** the user dismisses the prompt without picking a folder, **When** they reopen the app, **Then** they are offered again to save the pending capture.

---

### User Story 2 - No folder, no delete (Priority: P1)

The user has not chosen an output folder, or the field is empty. The app does not start a recording until they pick a folder, **or** if a capture already exists without a destination, it never deletes the working files just because the path is empty.

**Why this priority**: Explicit user rule: do not delete temps if a path is not defined.

**Independent Test**: Empty output folder blocks a new recording with a folder prompt; an existing unsaved session is not deleted.

**Acceptance Scenarios**:

1. **Given** an empty output folder field, **When** the user presses Record, **Then** they must choose a folder before capture starts.
2. **Given** working files from a capture and no valid destination, **When** processing ends, **Then** those files remain.

---

### User Story 3 - Bad path is corrected, not fatal (Priority: P1)

The chosen folder exists but cannot hold the finished file (path too long, not writable, drive gone). The app asks the user to correct the folder. It does not treat that as “delete the meeting.”

**Why this priority**: The 2026-09-09 failure was a too-long OneDrive path; the encoder reported “No such file or directory.”

**Independent Test**: A destination whose full file path is longer than Windows’ classic limit still results in a recoverable capture and a prompt to pick another folder (or a successful copy into that long folder if the OS allows it after writing somewhere short first).

**Acceptance Scenarios**:

1. **Given** a very long destination folder, **When** the user stops recording, **Then** the encoder does not write the finished file only at that long path as the first/only attempt.
2. **Given** the long folder cannot receive the file, **When** the user chooses Desktop or another short folder, **Then** the recording is saved there.
3. **Given** a destination that is not writable, **When** save fails, **Then** the user is asked to pick another folder and the working files remain.

---

### User Story 4 - Closing the app does not throw away an unsaved capture (Priority: P2)

The user stops recording, save fails, and they close the window. The working files survive. The next launch reminds them there is an unsaved recording and lets them choose a folder.

**Why this priority**: Closing the error dialog used to be the last moment before temps were already gone; now close must not finish the deletion.

**Independent Test**: After a failed save, quit and relaunch; the pending capture can still be saved.

**Acceptance Scenarios**:

1. **Given** an unsaved capture after a failed save, **When** the user quits, **Then** working files remain on disk.
2. **Given** those files, **When** the app starts, **Then** the user is prompted to save them to a folder they choose.

---

### Edge Cases

- Recording start fails before any media exists: empty working folder may be removed (nothing to lose).
- User refuses to pick a folder at start: recording does not begin.
- User picks a long folder at start: recording may still begin; save uses a safe local working copy first, then copy or prompt.
- Two pending sessions: prompt for each that still has media (oldest first is acceptable).
- Quit while recording: still offer stop-and-save; if that save fails, do not quit until the user has been told the files were kept (or they choose a folder).
- Working files live outside OneDrive sync so cloud dehydration cannot eat them.

## Requirements

### Functional Requirements

- **FR-001**: The app MUST NOT delete a recording session’s working files unless a finished recording file exists at a destination the user accepted and that file has been verified (present, non-empty, size matches the working finished file).
- **FR-002**: If the output folder is empty or not set, the app MUST require the user to choose a folder before a new recording starts.
- **FR-003**: If the destination is missing, not writable, or the finished file cannot be created there, the app MUST ask the user to choose another folder and MUST keep the working files.
- **FR-004**: Combining streams into the finished movie MUST first write to a short local working location that does not depend on the user’s OneDrive path length. Only after that file exists may the app copy it to the chosen folder.
- **FR-005**: A failed copy or failed combine MUST leave both the working session and, if already created, the local finished working file intact.
- **FR-006**: The app MUST remember an unsaved capture across restart and prompt the user to choose a destination.
- **FR-007**: Working capture files MUST be stored outside synced cloud folders (local app data), not in the system throw-away temp directory that Windows may clean.
- **FR-008**: Closing the app after a failed save MUST NOT delete the unsaved capture.
- **FR-009**: The user MUST be able to retry saving as many times as needed until a valid folder succeeds.
- **FR-010**: After a verified successful save, the app MAY delete the working session and the local working finished file.

### Key Entities

- **Recording session**: Working video/audio pieces for one capture until the finished file is verified.
- **Finished working file**: Combined movie written to a short local location.
- **Destination file**: Copy (or move) of the finished working file in the folder the user chose.
- **Pending save**: Durable reminder that a session is unsaved (so a restart can offer to finish).

## Success Criteria

### Measurable Outcomes

- **SC-001**: After any failed save, 100% of captures that had working media still have that media on disk until the user successfully saves or explicitly discards (this feature does not add a discard action; absence of discard is success).
- **SC-002**: A destination path longer than the classic Windows file-path limit cannot by itself cause the working capture to be deleted.
- **SC-003**: From a failed-save prompt, the user can complete a save to a valid folder in one folder-picker attempt without recording again.
- **SC-004**: After restart with an unsaved capture, the user sees a save prompt before they need to hunt for hidden folders.

## Assumptions

- The primary user records to folders that may live on OneDrive and may exceed Windows’ classic path length.
- There is no “discard recording” control in this change; keeping files forever until a good save is acceptable.
- A local short working copy is allowed even when the user wanted OneDrive; the user-visible file should still end up in their chosen folder when that folder can accept it.
- Empty session folders from a failed *start* (no media written) are not “recordings” and may be removed.
