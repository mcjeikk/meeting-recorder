# Contract: UI — Transcription Speed Presets

**Feature**: `002-transcription-speed-presets` | **Date**: 2026-07-27

## Control

- **Widget**: combo box or exclusive button group with three items (Spanish labels).
- **Placement**: same panel as “Transcribir al terminar…”.
- **Companion**: `QLabel` (or equivalent) showing `hint_es` for the current selection; updates immediately on change.

## Behavior

| Event | Expected |
|-------|----------|
| App start | Load `AppConfig.transcription_preset`; invalid → Equilibrado; set control + hint. |
| User changes preset | Update hint; save config immediately (same pattern as other prefs). |
| Enqueue after recording / manual enqueue | Snapshot current preset into job. |
| Job already queued/running | Changing UI preset does **not** alter that job. |
| During recording | Preset control remains usable (preference for *next* jobs); does not touch capture pipeline. |

## Accessibility / copy (ES)

| id | Label | Hint (approx.) |
|----|-------|----------------|
| rapido | Rápido | Más rápido; sin etiquetas de hablantes; mismo motor de reconocimiento que Equilibrado, búsqueda más ligera. |
| equilibrado | Equilibrado | Calidad habitual; con hablantes; en CPU suele rondar ~2× la duración del audio (varía según máquina). |
| maxima_calidad | Máxima calidad | Más lento; modelo de reconocimiento más pesado; con hablantes. |

## Non-goals (UI)

- No free-form model/beam editors in Phase 1.
- No language selector redesign.
- No progress UI changes beyond existing banner (optional: show preset name in stage text — nice-to-have).
