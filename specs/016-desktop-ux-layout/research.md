# Research: 016 Desktop UX layout

## R1 Accidental dropdown changes on wheel (FR-001)

**Decision**: Unfocused combo boxes ignore wheel; focused ones may still change. Click-to-focus (`StrongFocus`) so hover+wheel does not steal focus.

**Rationale**:
- Nielsen heuristic 5 (error prevention): do not let a high-frequency gesture (scroll) mutate settings.
- Qt default `QComboBox` changes the current item on hover-wheel even with `NoFocus` ([QTBUG-19730](https://bugreports.qt.io/browse/QTBUG-19730)). Community fix: `Qt::StrongFocus` plus ignore unfocused `Wheel` and let the parent scroll ([Qt Forum](https://forum.qt.io/topic/25072/how-to-ignore-the-mouse-wheel-event-when-combo-box-is-not-in-focus); [SO Qt6 ignore+return True](https://stackoverflow.com/questions/77347403/how-to-handle-qcombobox-wheel-events-with-an-event-filter)).
- Native HTML `<select>` in a scrolling page has the same complaint; modern product UIs require focus first.

**Alternatives rejected**: Disable wheel always (hurts keyboard-adjacent power users who clicked the combo). Leave default (user’s exact bug).

## R2 Primary action placement (FR-002)

**Decision**: Record/Stop + timer live in a non-scrolling chrome strip at the bottom. Settings (including preview) scroll above it.

**Rationale**:
- Fitts’s law: frequent, high-stakes control must stay large and reachable.
- Microsoft Win32 layout *Flow* and *Emphasis*: order UI for the task; emphasize the primary command ([Layout](https://github.com/MicrosoftDocs/win32/blob/docs/desktop-src/uxguide/vis-layout.md)).
- Windows 11 *calm / declutter* and elevation: separate command surface from content ([Design principles](https://learn.microsoft.com/en-us/windows/apps/design/design-principles)).

**Alternatives rejected**: Duplicate Record at top and bottom (noise). Tabs for Settings vs Record (extra click before every meeting).

## R3 Density (FR-003–006)

**Decision**: Drop wizard numbering. Collapse transcription extras behind a disclosure. Duplicate help → tooltips. Experimental mute: checkbox + tooltip only.

**Rationale**:
- Nielsen heuristic 8: dialogues must not contain rarely needed information.
- Win32 *progressive disclosure* and *lightest grouping that works* (avoid nested group boxes of essays).
- Preview currently uses vertical stretch **inside** the scroll widget, which inflates scroll height — treat preview as a bounded hero, not an Expanding filler.

**Alternatives rejected**: Two-column layout at 480px default width (too cramped). Remove experimental mute (constitution/product: stays experimental opt-in).

## R4 Startup fidget (FR-007)

**Decision**: Status strings that appear after `show` stay one line (elide). Wheel-guard stops “settings changing” while the user first-scrolls. Live meters may still move.

**Rationale**: Layout shift from wrapping `_WrapLabel` on mic-usage / system-route is perceived as controls jumping. WCAG-adjacent “don’t jump the layout”; Microsoft: sufficient space without cramped *or* reflowing chrome.

## R5 Constitution

Recording Always Wins, local-only, sibling transcription, no fused venv — layout-only change. Headless tests without `show()` still apply.
