# Feature Specification: A Mac installer that records and transcribes

**Feature Branch**: `030-macos-installer`

**Created**: 2026-10-23

**Status**: Draft

**Input**: "genera para este proyecto el instalable para MAC" — chosen options: the full product (record **and** transcribe, as on Windows); the target is a Mac with Apple Silicon; no Apple Developer account, so the app ships unsigned; the installer stays light and the transcription engine is downloaded and installed the first time it is needed.

## Context

- Today the product is Windows-only. Every piece that touches the operating system is Windows-specific: screen and window capture, system-audio capture, global shortcuts, hiding its own window from recordings, reacting to devices being plugged in, telling which apps hold the microphone, process priority, and the folders where it keeps its queue and settings.
- The capture layer was designed with a seam for other systems ("macOS (Fase 3)" in the roadmap), so the recording pipeline above it — mixing, the multi-track file, the "Mezcla" track, the transcription queue — is meant to be reused, not rewritten.
- Installation today means cloning a repository and building two Python environments by hand. That is acceptable for the current power user on Windows; it is not acceptable for a Mac installer, whose whole point is that someone can install and use it without a terminal.
- The transcription engine is about 2 GB of libraries plus about 3 GB of models. Putting it inside the installer was explicitly rejected: the installer must stay light and the engine is set up on first use.
- The app cannot be signed or notarized (no Apple Developer account). macOS therefore warns about it the first time it opens, and the instructions must walk the user past that warning.
- macOS requires the user to grant permissions before an app can see the screen, hear the system, or use the microphone. On Windows none of this exists; on macOS it is the first thing a user meets.
- The constitution was amended (1.1.0) to make macOS on Apple Silicon a supported platform. Its principles apply unchanged: recording always wins, everything stays on the machine, the engine stays a separate process with its own environment, and the queue survives closing the app.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Install and record a meeting on a Mac (Priority: P1)

As a Mac user I want to download one file, install the app by dragging it to Applications, grant the permissions it asks for, and record a meeting with my screen, the other participants' audio and my microphone, so that I get the same recording I would get on Windows.

**Why this priority**: Recording is the product. A recording that is lost cannot be recovered; a transcript can always be produced later. This story alone is a usable app.

**Independent Test**: On a Mac with Apple Silicon that never had the project, download the installer, install it, open it past the unsigned-app warning, grant the permissions, record two minutes of a video call, and open the resulting file.

**Acceptance Scenarios**:

1. **Given** the downloaded installer, **When** the user opens it, **Then** it offers to drag the app into Applications, and nothing else has to be installed to record (no terminal, no Python, no separate audio driver).
2. **Given** the app is opened for the first time, **When** macOS warns that it comes from an unidentified developer, **Then** the instructions shipped with the installer tell the user exactly how to open it anyway, in the current macOS wording.
3. **Given** the app lacks a permission it needs, **When** the user tries to record, **Then** the app says which permission is missing, what it is for, and opens the right settings page; it never starts a recording that would silently miss the screen or an audio source.
4. **Given** the permissions are granted, **When** the user records the whole screen or a single window, with system audio and microphone, **Then** the result is one video file with separate tracks for system audio, microphone and their mix, named as on Windows, with audio in sync with the video.
5. **Given** a recording in progress, **When** the user pauses, resumes, mutes the microphone or stops, **Then** it behaves as on Windows, including from the global shortcuts while another app has focus.
6. **Given** the app is quit or crashes during a recording, **When** it is opened again, **Then** the unsaved recording is offered for recovery, as on Windows.

---

### User Story 2 - Transcribe on a Mac, with the engine installed on first use (Priority: P1)

As a Mac user I want my recordings transcribed automatically, with speakers, without installing anything by hand, so that the Mac version is the same product and not just a recorder.

**Why this priority**: The user asked explicitly for the full product, and the engine-on-first-use decision only makes sense if that first use is guided and reliable.

**Independent Test**: On the same Mac, finish a recording; accept the offer to set up transcription; enter a Hugging Face token in the app; get the transcript with speakers; then quit and reopen the app and confirm no second setup happens.

**Acceptance Scenarios**:

1. **Given** the engine is not set up, **When** the first transcription is needed (after a recording or when importing a file), **Then** the app explains what will be downloaded, roughly how big it is and that it needs internet once, and asks before starting.
2. **Given** the user accepts, **When** setup runs, **Then** the app shows its progress, keeps working (recording stays possible and has priority), and the pending transcription starts by itself when setup ends.
3. **Given** setup fails or is interrupted (no connection, disk full, app quit), **When** the app is next opened or the user retries, **Then** it resumes or restarts cleanly and says what went wrong in plain words; a half-installed engine is never used.
4. **Given** no Hugging Face token, **When** the user wants speakers, **Then** the app lets them enter the token inside the app, explains the two prerequisites (account and accepting the model terms) with direct links, and checks the token before relying on it; the token is stored only on that Mac and never shown again in full.
5. **Given** the engine is set up, **When** recordings are queued, **Then** the queue, speakers, quality presets, PC-usage modes, estimates, retries and surviving an app quit behave as on Windows.
6. **Given** a recording starts while a transcription runs, **When** recording begins, **Then** the transcription pauses and resumes when recording ends, as on Windows.

---

### User Story 3 - Builds that do not depend on owning a Mac (Priority: P2)

As the maintainer, working on Windows, I want each change to produce a Mac installer and run the Mac checks automatically, so that I can publish Mac versions and notice when a change breaks the Mac build.

**Why this priority**: The maintainer has no Mac to build on. Without an automated build there is no installer at all; without automated checks the Mac version will rot (the same way the two-repository contract broke silently in spec 028).

**Independent Test**: Push a change; get a downloadable Mac installer and a green or red result for the Mac checks, without touching a Mac.

**Acceptance Scenarios**:

1. **Given** a change on the main branch, **When** it is pushed, **Then** a Mac installer is produced and the project's tests run on macOS.
2. **Given** a version is tagged, **When** the build finishes, **Then** the installer is attached to a release page with its version, so a user downloads it from one stable place.
3. **Given** a change that breaks the Mac build or its tests, **When** it is pushed, **Then** the result is visibly red.

---

### User Story 4 - Windows keeps working exactly as today (Priority: P1)

As the current Windows user I want nothing to change for me, so that the Mac work cannot cost me a meeting.

**Independent Test**: Run the Windows test suites and the existing recording and transcription verification on the Windows machine after the change.

**Acceptance Scenarios**:

1. **Given** the Mac support is merged, **When** the Windows app is used, **Then** capture, transcription, settings, queue and installation steps are unchanged, and all existing checks pass.

### Edge Cases

- The user denies a permission, or grants it and macOS only applies it after the app restarts: the app must tell which one and that a restart is needed, not fail silently.
- Each new unsigned version may be treated by macOS as a different app, so permissions might be asked again after an update: the instructions must say so.
- Bluetooth headsets and external displays are plugged in or out while the app is open or recording.
- A window chosen for capture is closed or minimized during the recording.
- The user has several displays with different resolutions; Mac displays have high pixel density, so file size and smoothness must stay reasonable.
- Not enough free disk for the engine (around 5 GB counting the models) or for the recording.
- No internet the first time a transcription is needed: recording keeps working, and transcriptions wait in the queue until setup can happen.
- The engine's download source changes versions: the engine installed must be the one validated for the app version, not whatever is newest that day.
- The app is run from the installer image without being copied to Applications, or moved after installing.
- Windows-only options with no Mac equivalent: they are hidden on Mac rather than shown as broken.

## Requirements *(mandatory)*

### Functional Requirements

**Installation**

- **FR-001**: The project MUST produce a single downloadable installer for Macs with Apple Silicon running macOS 13 or later, containing the app, that installs by dragging it into Applications.
- **FR-002**: Recording MUST work after installing it, with nothing else to install and without using a terminal.
- **FR-003**: The installer MUST include short instructions for opening an unsigned app the first time and for granting permissions, matching the current macOS wording.
- **FR-004**: The installer MUST stay small enough to download comfortably: it MUST NOT contain the transcription engine or its models.

**Recording**

- **FR-005**: On Mac the app MUST record the whole screen (any display) or one window, together with system audio and microphone, into the same multi-track file the Windows version produces (separate system, microphone and mix tracks, same names, mix used for transcription).
- **FR-006**: System audio MUST be captured without the user installing a separate audio driver.
- **FR-007**: The app MUST detect missing screen, system-audio or microphone permissions before recording, name the missing one, and take the user to the place to grant it.
- **FR-008**: Pause, resume, mute, stop, level meters, preview, device selection, recovery of unsaved recordings and automatic audio/video synchronisation MUST work on Mac as on Windows.
- **FR-009**: Global shortcuts for start/stop, pause/resume and mute MUST work on Mac while another app has focus, with Mac-appropriate key combinations.
- **FR-010**: The option to keep the app's own window out of recordings MUST work on Mac.
- **FR-011**: Plugging or unplugging audio devices MUST be noticed on Mac as on Windows.
- **FR-012**: Features that cannot be offered on Mac MUST be hidden there, and each such gap MUST be listed in the documentation.

**Transcription**

- **FR-013**: The first time a transcription is needed, the app MUST offer to set up the engine, stating download size and that internet is needed once, and MUST only proceed with the user's consent.
- **FR-014**: Engine setup MUST run in the background with visible progress, MUST yield to recording, MUST survive interruption without leaving a usable-looking broken engine, and MUST install the engine version validated for that app version.
- **FR-015**: The engine MUST keep running as a separate process with its own environment, invoked the same way as on Windows; the app MUST NOT load it into itself.
- **FR-016**: The user MUST be able to enter, check and replace the Hugging Face token inside the app; it MUST be stored only on that machine, outside the app bundle, and never displayed in full after entry.
- **FR-017**: Queue, speakers, presets, PC-usage modes, estimates, retries, pausing for recordings and surviving app quit MUST behave on Mac as on Windows.
- **FR-018**: Settings, queue, logs and working files MUST live in the Mac's per-user application-data location, outside any folder the user syncs.

**Build and quality**

- **FR-019**: Every push to the main branch MUST build the Mac installer and run the project's tests on macOS, without the maintainer needing a Mac.
- **FR-020**: A tagged version MUST publish its Mac installer on a release page.
- **FR-021**: The Windows app, its installation and its checks MUST be unchanged by this feature.

### Key Entities

- **Installer**: the downloadable file for Mac; has a version; contains the app and the first-run instructions, not the engine.
- **Engine installation**: the transcription engine set up on a given Mac; has a state (absent, installing, ready, broken), a version tied to the app version, and a location in the user's application data.
- **Permission**: screen, system audio, microphone; each granted or not; each needed for a specific part of a recording.
- **Hugging Face token**: the user's secret for speaker identification; stored on the machine, never in the app bundle or the repository.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a Mac with Apple Silicon that never had the project, a person following only the instructions in the installer goes from download to a finished two-minute recording in under 10 minutes, without a terminal.
- **SC-002**: That recording has video, system audio and microphone on separate tracks plus the mix, with audio and video within 100 ms of each other at start and end.
- **SC-003**: From accepting the engine setup to the first transcript with speakers takes under 30 minutes on a typical home connection, with no terminal, and reopening the app afterwards asks for nothing again.
- **SC-004**: An interrupted engine setup (network cut midway) recovers on retry and ends in a working engine, in one attempt.
- **SC-005**: Every push to the main branch yields a Mac installer and a macOS test result within 30 minutes, with no manual step.
- **SC-006**: All existing Windows checks still pass after the change.
- **SC-007**: The installer is under 500 MB.

## Assumptions

- Target: Macs with Apple Silicon only. Intel Macs are out of scope.
- Supported: macOS 13 Ventura and later (the user does not know the target Mac's version and asked for the widest support). 13 is the oldest version where the system lets an app capture system audio without a separate driver. If a capability only exists on newer versions, the app uses it there and keeps a working path on 13.
- The maintainer has no Mac to build on; builds run on a hosted macOS build service tied to the existing repository. Real capture (screen, system audio, microphone, permissions) cannot be verified there and is verified on the user's Apple Silicon Mac.
- Unsigned app: macOS shows a warning the first time and may ask for permissions again after each update. Signing and notarization are a later, separate decision, already listed in the roadmap ("Fase 5").
- Mac shortcuts default to Control+Option+R (record/stop), Control+Option+P (pause) and Control+Option+M (mute), to avoid the Command+Shift combinations that browsers and meeting apps already use.
- Transcription on Mac runs on the processor, like on Windows today; using the Mac's graphics chip for speed is a later improvement, not part of this feature.
- The engine is downloaded from the public package sources it already uses on Windows, pinned to the validated versions; models come from Hugging Face on first transcription, as today.
- Windows-only behaviour that may have no Mac equivalent (for example, naming which other apps are using the microphone) is hidden on Mac and documented as a gap, per FR-012.
