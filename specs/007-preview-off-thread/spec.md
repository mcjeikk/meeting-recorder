# Feature Specification: Lightweight Off-Thread Preview

**Feature Branch**: `007-preview-off-thread`

**Created**: 2026-07-28

**Status**: Draft

**Input**: User description: "Preview more lightweight / off UI thread — don't block Qt on grab."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - UI stays responsive while preview refreshes (Priority: P1)

While the app is idle (or recording), the preview thumbnail updates without freezing window drag, button clicks, or meter animation for the duration of a heavy window/screen grab.

**Why this priority**: `grab_window_frame` / screen grabs can stall the Qt GUI thread today.

**Independent Test**: Select a GPU-accelerated window source; interact with UI while preview refreshes — clicks remain responsive; preview eventually updates.

**Acceptance Scenarios**:

1. **Given** idle with a window source, **When** preview refresh runs, **Then** grab work is not performed synchronously on the GUI thread.
2. **Given** a slow grab, **When** the user clicks mute/refresh, **Then** the click is handled without waiting for the grab to finish.
3. **Given** overlapping refresh ticks, **When** a grab is already in flight, **Then** at most one extra refresh is queued (no grab stampede).

---

### User Story 2 - Preview still correct (Priority: P1)

Preview content remains correct for window and selected monitor (006), and while recording uses the live capture frame when available.

**Acceptance Scenarios**:

1. **Given** window source idle, **When** preview completes, **Then** thumbnail shows that window.
2. **Given** screen source with monitor_index, **When** preview completes, **Then** thumbnail matches that screen.
3. **Given** recording with live frames, **When** preview ticks, **Then** uses recorder frame path without starting a second WGC session when possible.

### Edge Cases

- Grab fails → leave previous pixmap or empty; no crash.
- Source changes mid-grab → discard stale result (generation token).
- App closing mid-grab → no crash / no emit to destroyed widgets.

## Requirements *(mandatory)*

- **FR-001**: Heavy idle grabs (WGC one-shot) MUST run off the Qt GUI thread.
- **FR-002**: UI updates (QPixmap on QLabel) MUST occur on the GUI thread via queued signal.
- **FR-003**: Overlapping refreshes MUST be coalesced (pending + dirty flag or equivalent).
- **FR-004**: Stale grabs after source change MUST NOT overwrite newer previews.
- **FR-005**: Scaling SHOULD use a lightweight transform (avoid unnecessary SmoothTransformation cost).

## Success Criteria

- **SC-001**: GUI thread does not call `grab_window_frame` / WGC start synchronously from the timer tick path.
- **SC-002**: Preview still updates within a couple of refresh cycles under normal load.
- **SC-003**: Headless MainWindow constructs without error.

## Assumptions

- `QImage` may be constructed off-thread from buffer copy; `QPixmap`/`QLabel` stay on GUI thread (Qt docs).
- Screen idle preview can use WGC one-shot by monitor_index (same as windows) to avoid GUI-thread `grabWindow`.
