# Implementation Plan: Calmer Desktop Recording Layout

**Branch**: `016-desktop-ux-layout` | **Date**: 2026-09-09 | **Spec**: [spec.md](./spec.md)

## Summary

Stop unfocused combo boxes from eating the mouse wheel. Put Record/Stop + timer in a sticky chrome strip. Shorten the settings column: bounded preview, no numbered wizard, transcription extras behind a disclosure, help in tooltips, one-line status.

## Technical Context

**Language/Version**: Python 3.11.9

**Primary Dependencies**: PySide6

**Storage**: Existing `AppConfig` (no new required keys)

**Testing**: unittest, `QT_QPA_PLATFORM=offscreen`

**Target Platform**: Windows desktop (PySide6)

**Project Type**: desktop-app

**Constraints**: Headless MainWindow without `show()`; Recording Always Wins; experimental mute stays opt-in off

**Scale/Scope**: `app/ui/main_window.py` + small helpers + tests

## Constitution Check

- I PASS — recording controls stay more reachable, not deferred
- II PASS — no cloud
- III PASS — transcription UI only
- IV PASS — no new subprocesses
- V PASS — layout simplification, not a new architecture

## Project Structure

```text
specs/016-desktop-ux-layout/
app/ui/scroll_guard.py
app/ui/disclosure.py
app/ui/main_window.py
tests/test_scroll_guard.py
tests/test_desktop_ux_layout.py
```

## Phase 0 / 1

See [research.md](./research.md). No new data model. Contract: unfocused wheel is a no-op on combos; chrome hosts Record.

## Implementation notes

1. `WheelFocusFilter`: on `QEvent.Wheel`, if widget is `QComboBox` without `hasFocus()`, `event.ignore(); return True`. `setFocusPolicy(StrongFocus)`.
2. Shell: `QVBoxLayout` → `QScrollArea` (settings) + `QWidget#chrome` (record, pause, timer, status, busy, banners).
3. Preview `maximumHeight` ~200; no stretch factor inside the scroll widget.
4. `Disclosure` tool button + body for preset/impact/language/speakers (QFormLayout).
5. Hints → combo/checkbox tooltips; `_tx_file_hint` stays a short line mentioning Carpeta de salida.
6. Mic-usage and system-route: single-line labels, no word-wrap.
