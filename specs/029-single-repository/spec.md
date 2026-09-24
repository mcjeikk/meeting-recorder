# Feature Specification: Recorder and Transcriptor live in one repository

**Feature Branch**: `029-single-repository`

**Created**: 2026-09-24

**Status**: Draft

**Input**: "Como la herramienta de transcripción y el recorder funcionan de forma conjunta, ¿por qué no lo unificamos en un solo repo?" — chosen option: one repository with the Transcriptor in a subfolder, its history preserved, two environments and the subprocess kept as they are.

## Context

- The Recorder and the Transcriptor are separate repositories, but they share a contract that neither repository can test on its own: the Recorder reads the Transcriptor's log line by line for phases and percentages, relies on `TRANSCRIPTOR_PLAIN=1`, sends several files in one call, expects a prepared WAV to be used as is, and reads the speaker map of `transcripcion.json`.
- That contract broke silently in practice (spec 028): the published Recorder relied on Transcriptor features that had never been published, so any queue of two or more files failed on a fresh install. Two repositories let one side move without the other.
- A newcomer has to clone two repositories into the right relative layout for transcription to work at all.
- The decision to run the Transcriptor as a **subprocess with its own environment** stays. It is what keeps torch and pyannote out of the app (pyannote already broke its API between 3.x and 4.x), what lets a transcription survive the app closing, and what lets it be suspended while recording. Unifying the repository must not unify the environments.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One clone gives the whole product (Priority: P1)

As someone new to the project I want a single repository that records and transcribes, so that I cannot end up with mismatched versions or a layout the app does not recognise.

**Independent Test**: Clone the one repository into a clean folder, follow its README, and transcribe a sample with speakers without any configuration.

**Acceptance Scenarios**:

1. **Given** one fresh clone, **When** both parts are installed as the README says, **Then** the app finds the Transcriptor inside the repository with no configuration and transcribes with speakers.
2. **Given** a change to the contract between the two parts, **When** it is committed, **Then** both sides change in the same commit and one command runs the tests of both.

---

### User Story 2 - Nothing already working breaks (Priority: P1)

As the current user I want my installation to keep transcribing throughout the move, so that the change is invisible except for where the files live.

**Independent Test**: Keep transcribing with the existing setup while the repository changes, then switch to the bundled Transcriptor and verify.

**Acceptance Scenarios**:

1. **Given** the Transcriptor inside the repository has no environment installed yet, **When** a transcription starts, **Then** the app keeps using a complete Transcriptor it can find elsewhere rather than choosing the incomplete one.
2. **Given** an existing installation with the Transcriptor as a sibling folder, **When** the app updates, **Then** it keeps working without changes.
3. **Given** the bundled Transcriptor is installed, **When** it is complete, **Then** it is preferred over sibling copies.
4. **Given** the Transcriptor's history, **When** it moves into the repository, **Then** each of its files keeps its history.
5. **Given** the old Transcriptor repository, **When** someone lands on it, **Then** it says where the project lives now and accepts no further changes.

---

### User Story 3 - The Transcriptor stays usable on its own (Priority: P2)

As someone who only wants to transcribe files from the command line I want the Transcriptor to keep working by itself from its folder, so that the move takes nothing away.

**Acceptance Scenarios**:

1. **Given** the Transcriptor's folder inside the repository, **When** its command line or its `.bat` shortcuts are used, **Then** they work exactly as before.

### Edge Cases

- The bundled folder exists (it is in every clone) but has no environment: it must never be picked over a complete Transcriptor, and it must not be reported as available.
- A saved path that points to a complete Transcriptor always wins; a saved path that is incomplete is replaced by a complete one if there is any.
- The user's own files in the old Transcriptor folder (results, input audio, the token) are not versioned and must not be lost or published.
- The token file must stay out of the repository in its new location too.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Transcriptor MUST live in a subfolder of the Recorder repository, with its full history, each file's history reachable under its new path.
- **FR-002**: Each part MUST keep its own environment; the Recorder MUST keep invoking the Transcriptor as a subprocess and MUST NOT import it.
- **FR-003**: Autodetection MUST prefer the bundled Transcriptor, and MUST consider a candidate usable only when both its command line and its environment are present.
- **FR-004**: Existing sibling layouts MUST keep being found, as fallbacks.
- **FR-005**: A saved path to a complete Transcriptor MUST win; an incomplete saved path MUST yield to a complete candidate.
- **FR-006**: The installation instructions MUST describe one clone and both environments, in order, from nothing to a transcript with speakers.
- **FR-007**: One documented command MUST run the tests of both parts, each in its own environment.
- **FR-008**: The old Transcriptor repository MUST point to the new location and be archived.
- **FR-009**: The Transcriptor's command line and shortcuts MUST keep working from their new folder.
- **FR-010**: Secrets, environments and media MUST stay out of version control in the new layout.

## Success Criteria *(mandatory)*

- **SC-001**: A single fresh clone, installed as its README says, with an empty app configuration, transcribes a sample with speakers.
- **SC-002**: `git log` of a Transcriptor file under its new path shows its commits from before the move.
- **SC-003**: With the bundled Transcriptor lacking its environment, the current installation keeps transcribing through the sibling copy.
- **SC-004**: After installing the bundled environment and pointing the configuration to it, the current installation transcribes with speakers.
- **SC-005**: One command runs both test suites and reports both green.
- **SC-006**: The old repository shows the pointer and is archived.

## Assumptions

- The bundled folder is named `transcriptor/`, the name the project already uses for it.
- The user's current `Apps\Transcriptor` folder is left in place after the move; deleting it is the user's call once the bundled one is verified, since it holds unversioned results.
- Environments cannot be moved safely on Windows (launchers embed their path), so the bundled environment is created fresh; the downloaded models are shared through the Hugging Face cache and are not downloaded again.
