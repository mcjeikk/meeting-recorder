# Feature Specification: Calmer Desktop Recording Layout

**Feature Branch**: `016-desktop-ux-layout`

**Created**: 2026-09-09

**Status**: Implemented

**Input**: User: the GUI feels too long and dense; on launch controls keep changing; the mouse wheel over dropdowns changes settings when the user meant to scroll the window. Review the UI against industry UX standards and apply evidenced improvements.

## User Scenarios & Testing

### User Story 1 - Scroll does not hijack settings (Priority: P1)

The user opens the app and rolls the mouse wheel to see what is below. Dropdowns under the pointer must **not** change source, microphone, quality, language, speakers, or PC use. The window (or the page) scrolls instead. A dropdown only changes with the wheel after the user has focused it (click or keyboard).

**Why this priority**: Accidental setting changes are a classic error-prevention failure and match the reported frustration.

**Independent Test**: With an unfocused dropdown, a wheel gesture leaves its value unchanged.

**Acceptance Scenarios**:

1. **Given** a dropdown that is not the focused control, **When** the user rolls the wheel over it, **Then** its value stays the same and the page can scroll.
2. **Given** the user has clicked a dropdown so it is focused, **When** they roll the wheel, **Then** the list may change (intentional).

---

### User Story 2 - Record is always in reach (Priority: P1)

Starting or stopping a recording does not require scrolling past a wall of transcription and help text. The primary record/stop control and the elapsed time stay visible while the user adjusts capture settings.

**Why this priority**: The app’s job is recording; Microsoft layout guidance and Fitts’s law put the primary action on a stable, nearby surface.

**Independent Test**: With a short window, capture settings may scroll; Record/Stop remains on screen.

**Acceptance Scenarios**:

1. **Given** a window shorter than the full settings list, **When** the user scrolls settings, **Then** Record/Stop and the timer remain visible.
2. **Given** the user is recording, **When** they scroll settings, **Then** Stop and Pause remain visible.

---

### User Story 3 - Less density, same power (Priority: P1)

The first screen emphasizes capture (what to record, mic, system audio, save folder) without a long numbered form. Transcription details (quality, PC use, language, speakers) sit behind a disclosure the user opens when needed. Repeated paragraphs of help move to tooltips. Experimental mute stays available without a second essay.

**Why this priority**: Nielsen’s aesthetic/minimalist heuristic and Windows progressive disclosure: hide rarely needed options; keep the frequent path short.

**Independent Test**: Quality/language/speakers are not all permanently expanded; every previous setting remains reachable.

**Acceptance Scenarios**:

1. **Given** a first-time look at the window, **When** transcription extras are collapsed, **Then** the capture path is shorter than today’s stacked hints + four full dropdown blocks.
2. **Given** the user opens transcription options, **When** they change quality, language, speakers, or PC use, **Then** those choices still apply to the next recording or import.

---

### User Story 4 - Startup does not fidget (Priority: P2)

After the window appears, dropdown values the user already saved must not jump because of hover-scroll or because help lines appear and shove controls. Status lines that fill in (mic in use, system route) must not inflate the layout by wrapping into extra paragraphs.

**Why this priority**: Perceived instability at launch is the second complaint; reduce layout shift, not live meters (those should still move).

**Independent Test**: Saved dropdown values survive a wheel over them; status text stays one line.

**Acceptance Scenarios**:

1. **Given** saved microphone and quality, **When** the window is shown, **Then** those values are the ones displayed (meters may animate).
2. **Given** a long system-route or mic-usage message, **When** it appears, **Then** it occupies a single line (may elide), not a growing block of wrap.

---

### Edge Cases

- Keyboard users can still change a focused dropdown with arrow keys and, if focused, the wheel.
- Recording Always Wins: source stays locked while recording; file import still works.
- Empty transcription queue: a short empty hint, not a large blank list plus a paragraph.
- Very short windows: settings scroll; chrome (record) stays usable.
- Dropping files onto the window still queues transcription.

## Requirements

- **FR-001**: An unfocused dropdown MUST ignore the mouse wheel for changing its value so the user can scroll the window.
- **FR-002**: Record/Stop and elapsed time MUST remain visible while settings scroll (stable chrome).
- **FR-003**: Capture settings (source, microphone, system audio, output folder) MUST remain on the main path without a wizard-style 1–2–3–4 numbering.
- **FR-004**: Transcription quality, PC use, language, and speakers MUST be available without occupying the default vertical stack; a disclosure (or equivalent) reveals them.
- **FR-005**: Duplicate or lengthy help that repeats a control’s purpose MUST move to a tooltip (or equivalent on-demand text); one short on-screen hint is enough for import/output.
- **FR-006**: Experimental follow-meeting mute MUST remain opt-in and off by default; its long explanation MUST NOT sit as a second visible paragraph.
- **FR-007**: Dynamic status (mic in use, system route) MUST NOT grow the form by wrapping into multiple new lines.
- **FR-008**: Existing capture, mute, transcription queue, import, and recording behaviors MUST keep working.

## Success Criteria

- **SC-001**: Automated test: wheel over an unfocused dropdown does not change its index.
- **SC-002**: Automated test: Record/Stop lives in a chrome region that is not the scrolling settings pane.
- **SC-003**: Automated test: transcription extras (quality/PC/language/speakers) are not all visible until the disclosure is opened (or equivalent).
- **SC-004**: Existing headless UI tests (import button, queue list, speakers control, preview smoke) still pass.

## Assumptions

- Single power-user Windows desktop (constitution V); no new platforms.
- Primary task is record; transcription is important but secondary on first paint.
- Industry sources: Nielsen heuristic 5 (error prevention) and 8 (minimalist design); Microsoft Win32 layout (flow, grouping, progressive disclosure, emphasis); Windows 11 calm/declutter; Qt community practice that dropdowns must use click-to-focus before wheel-changing values (`QTBUG-19730` / common StrongFocus + ignore-unfocused-wheel pattern).
- Live VU meters may keep moving; that is feedback, not “settings changing.”
