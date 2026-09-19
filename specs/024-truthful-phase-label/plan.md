# Implementation Plan: The notice names the phase that is actually running

**Branch**: `024-truthful-phase-label` | **Date**: 2026-09-18 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/024-truthful-phase-label/spec.md`

## Summary

`cli_progress.parse_plain_chunk` learns the two engine announcements it was ignoring (`- Transcribiendo (modelo …)` and the end-of-transcription markers) and stops treating "the audio needed no conversion" as a phase. The parse result gains an explicit `phase` (`prepare` / `asr` / `speakers` / `saving`); the Spanish label becomes a lookup from that phase, in one place. `worker._monitor` then keys its "the engine's percentage does not apply here" rule on the phase instead of searching for the word `hablantes` in the label, which is the hidden text-to-behavior coupling this feature removes. No change to the engine, the queue, the estimate model or the UI layout.

## Technical Context

**Language/Version**: Python 3.11.9 (Recorder `.venv`)

**Primary Dependencies**: standard library `re`. No new dependency, no Qt in the parsing path.

**Storage**: none. Phases are derived per poll from the log; nothing is persisted.

**Testing**: unittest over pure text (`tests/test_cli_progress.py`): the full real-log replay, each announcement, the short-file case with no percentage, unknown lines leaving state untouched, multi-phase chunks, batch file switches. Plus `tests/test_batch_tracking.py` to confirm the worker's indeterminate-percentage rule still holds when driven by phase.

**Target Platform**: Windows desktop (Grabador)

**Project Type**: Desktop app (PySide6) + sibling CLI subprocess

**Performance Goals**: unchanged; the parser already runs per poll over a small chunk, and gains two regexes.

**Constraints**: backwards compatible with the existing 4-tuple consumers (the worker is the only one); unmatched lines must never blank the label; the pause label keeps precedence; no behavior may depend on display wording after this change.

**Scale/Scope**: one parser, one worker rule, labels in one table.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- I. Recording Always Wins — PASS (parsing only; the pause path and its label are untouched and keep precedence)
- II. Privacy Is Local — PASS (reads a local log, shows local text)
- III. Transcription stays a sibling subprocess — PASS (this is a *reading* change; the engine's contract is matched more completely, never altered)
- IV. Robust paths and processes — PASS (no subprocess, no paths; unmatched input degrades to "no change")
- V. Simplicity — PASS (two regexes, one label table, one rule moved from text to value; no new module)
- Verification & Quality — PASS (every criterion is checkable by replaying log text; `verify_transcription.py --quick` confirms the sequence against the real engine)

Post-design re-check: unchanged. Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/024-truthful-phase-label/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/phase-labels.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
app/transcription/cli_progress.py    # phases + labels in one table; two new announcements matched
app/transcription/worker.py          # indeterminate-percentage rule keyed on phase, not on label text
CLAUDE.md                            # the phase table as the reading contract of the log

tests/test_cli_progress.py           # real-log replay, per-announcement, short file, unknown lines
tests/test_batch_tracking.py         # the worker rule still holds, now driven by phase
```

**Structure Decision**: keep everything in `cli_progress.py` — it is already the single place that knows the engine's output — and export the phase constants so the worker can compare values instead of strings. No new module for four constants and a dict.

## Complexity Tracking

> No constitution violations; section intentionally empty.
