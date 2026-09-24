# Feature Specification: Someone who clones both repositories can record and transcribe

**Feature Branch**: `028-fresh-clone-transcribes`

**Created**: 2026-09-24

**Status**: Draft

**Input**: "Necesito que ya quede lista para que cualquier persona la baje, la configure, y pueda no solo grabar sino transcribir las grabaciones."

## Context

Reviewing the project as a newcomer would, following both READMEs literally, found four things that stop transcription on a fresh machine even though everything works on the author's:

1. **The published Transcriptor was older than the one in use.** Its CLI accepted a single input file. The Recorder sends every compatible pending file in one call, so any queue of two or more files failed as a whole, and the retries failed the same way. The fix existed locally, uncommitted since 2026-09-10, together with the exclusive speaker mode and the pyannote pin the Recorder's documentation relies on.
2. **The Transcriptor was not found where `git clone` puts it.** Cloning both repositories yields `meeting-recorder\` and `meeting-transcriber\` side by side; autodetection only looked for a folder called `Transcriptor`.
3. **Opening the app before installing the Transcriptor broke it later.** The first launch saves an empty `transcriptor_dir`. The availability check then autodetects and answers "available", but the worker launches the CLI with the saved empty path.
4. **The first verification step fails for a newcomer.** `verify_transcription.py --quick` samples "the last recording", and a new user has none; the error said so and nothing more.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Clone, install, transcribe (Priority: P1)

As someone new to the project I want to clone both repositories, follow the instructions once, and have recordings transcribed with speakers, without editing configuration files by hand.

**Independent Test**: On a clean folder and a fresh app configuration, clone both repositories from GitHub, follow the README, and transcribe a sample with speakers.

**Acceptance Scenarios**:

1. **Given** both repositories cloned side by side with their default folder names, **When** the app starts, **Then** it finds the Transcriptor with no configuration.
2. **Given** several recordings queued together, **When** they are transcribed, **Then** they are processed in one run and all of them produce a transcript.
3. **Given** the app was opened before the Transcriptor was installed, **When** a transcription starts, **Then** the Transcriptor is found and used.
4. **Given** a saved Transcriptor path that no longer exists, **When** a transcription starts, **Then** the Transcriptor is looked for again rather than launched from the stale path.
5. **Given** a newcomer with no recordings yet, **When** they run the verification, **Then** the message tells them how to verify with any audio file or a short test recording.

### Edge Cases

- A path the user set explicitly and that still holds a Transcriptor always wins over autodetection.
- If no Transcriptor is found anywhere, the saved path is kept so the error names it.
- A folder with the right name but without the CLI is not a Transcriptor.
- The development layout (`Transcriptor\`, and the legacy location one level up) keeps working.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The published Transcriptor MUST accept several input files in one call and MUST carry the behaviour the Recorder documents (exclusive speakers, reused models, no reconversion of prepared WAVs, the thread cap).
- **FR-002**: Autodetection MUST find the Transcriptor under the folder name `git clone` creates, as well as the existing names and locations.
- **FR-003**: A saved Transcriptor path that is empty or no longer valid MUST be replaced by autodetection, both when the configuration loads and when each job starts.
- **FR-004**: A valid saved path MUST take precedence over autodetection.
- **FR-005**: The CLI MUST never be launched from a path that failed the availability check.
- **FR-006**: The verification script MUST tell a user without recordings how to verify anyway, and a user without a Transcriptor where it is expected.
- **FR-007**: The installation instructions MUST describe one ordered path from nothing to a transcript with speakers, including the Python version, the side-by-side layout, the Hugging Face token and model terms, and the first model download.

## Success Criteria *(mandatory)*

- **SC-001**: In a clean folder, with a fresh app configuration, cloning both repositories from GitHub and following the READMEs yields a transcript with speakers, with no manual configuration.
- **SC-002**: The Transcriptor cloned from GitHub accepts two files in one call and writes both transcripts.
- **SC-003**: A configuration saved with an empty or stale Transcriptor path transcribes once the Transcriptor exists beside the Recorder.
- **SC-004**: Both test suites pass on the fresh clones.

## Assumptions

- Windows and Python 3.11, as the Transcriptor's dependencies require.
- Speaker identification requires each user's own Hugging Face token; it is never shipped in the repositories.
- Model downloads (about 1.5 GB for the default quality) happen once, on first use.
