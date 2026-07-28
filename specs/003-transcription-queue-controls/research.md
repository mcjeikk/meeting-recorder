# Research: Transcription Queue Controls

**Feature**: `003-transcription-queue-controls`  
**Date**: 2026-07-27

## Evidence Review (codebase-first)

### E1 — What the UI already does

| Claim | Verdict | Sources | Implication |
|-------|---------|---------|-------------|
| Banner shows live stage/progress | Confirmed | `main_window._on_tx_update` | Extend banner; don’t invent a new panel |
| Retry / Open / Ver log exist | Confirmed | `_tx_retry_btn`, `_open_transcription`, `_open_tx_log` | Keep; add Cancel + Clear |
| ✕ closes banner only | Confirmed | `setVisible(False)` on close | Document: hide ≠ cancel |

### E2 — Cancel gap

| Claim | Verdict | Sources | Implication |
|-------|---------|---------|-------------|
| No cancel API | Confirmed | `JobStore` / `TranscriptionWorker` public API | Need `cancel` + process stop |
| `shutdown()` doesn’t kill child | Confirmed | worker docstring | By design for app close; cancel is different (user intent) |
| psutil already monitors PID | Confirmed | `_monitor` | Reuse for terminate on cancel |

### E3 — Language

| Claim | Verdict | Sources | Implication |
|-------|---------|---------|-------------|
| Config has `transcription_language` | Confirmed | `AppConfig` | Wire UI only + normalize |
| CLI accepts `--language` | Confirmed | `integration.build_command` | `es`/`en`/`auto` sufficient MVP |
| No UI control | Confirmed | `main_window` TX section | Add combo near presets |

### E4 — Desktop UX patterns (light)

Common desktop/media apps expose **Cancel** on the active item, **language before start**, and **clear failed** without a full job board. Full history is a separate feature (deferred).

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| D1 Cancelled status | New `cancelled` | Distinct from `error` (Retry vs Clear) |
| D2 Kill policy | terminate then kill if needed | User asked to stop CPU; app-close still leaves orphans by design |
| D3 Language set | `es`, `en`, `auto` | Matches config comment + CLI |
| D4 Clear scope | `error` + `cancelled` only | Don’t delete pending/running/done |
| D5 History UI | Out of scope | Spec FR-011 / simplicity |

## Alternatives rejected

- Soft-cancel only (leave process running): fails SC-002.
- Full queue list widget: over-scope for single-user sequential worker.
- Editing language on in-flight job: conflicts with snapshot model (same as presets).
