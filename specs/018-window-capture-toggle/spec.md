# Feature Specification: Toggle whether this window is captured

**Feature Branch**: `018-window-capture-toggle`

**Created**: 2026-09-16

**Status**: Draft

**Input**: User description: the app must have a checkbox so the user can choose whether the Recorder window is “transparent” to capture (not appear in recordings or screenshots) or not.

## Clarifications

### Session 2026-09-16

Today the Recorder always calls Windows display-affinity exclude-from-capture, so the window never appears in its own recordings or OS screenshots. The user wants that to be a choice, not a hard-coded hide.

- Q: What does “transparente” mean? → A: Hidden from screen/window capture and screenshots, not a see-through UI.
- Q: Default? → A: Hidden (same as today). Uncheck to include this window in recordings and screenshots.
- Q: Apply immediately? → A: Yes, including mid-recording. Persist across restarts.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Choose if this window is in the picture (Priority: P1)

As the primary user, I record the screen or a window and I do not want the Grabador covering the meeting. I can also uncheck a control so the Grabador **does** appear (for a demo, a screenshot of the app, or a recording that should show the UI).

**Why this priority**: Capture of this window is currently forced off with no way back.

**Independent Test**: With the box checked, this window is excluded from capture. Unchecking includes it. The choice is still there after restart.

**Acceptance Scenarios**:

1. **Given** the default (or checked) state, **When** the user records the full screen or takes an OS screenshot, **Then** the Grabador window is not in the image.
2. **Given** the box is unchecked, **When** they record the screen or screenshot, **Then** the Grabador window is visible in the image.
3. **Given** a saved choice, **When** they restart the app, **Then** the same box state is selected and applied.

---

### Edge Cases

- Toggle while already recording: affinity updates immediately; no need to stop.
- HWND not ready yet: apply again when the window is shown.
- Non-Windows: the checkbox may exist but is a no-op (product is Windows-first).

## Requirements *(mandatory)*

- **FR-001**: The Recorder MUST expose a persisted checkbox that chooses whether **this** window is excluded from recordings and screenshots.
- **FR-002**: The default MUST be excluded (current behavior).
- **FR-003**: Changing the checkbox MUST apply at once and MUST be remembered.
- **FR-004**: Existing capture of other windows/monitors, audio, and transcription MUST be unchanged.

## Success Criteria *(mandatory)*

- **SC-001**: Unit test maps checked → exclude flag, unchecked → none.
- **SC-002**: Headless UI: checkbox present, default on, toggling updates the saved preference.

## Assumptions

- Single power user; one checkbox on the capture settings path, short label + tooltip (spec 016).
