# Implementation Plan: An overnight queue leaves a trail you can read in the morning

**Branch**: `026-overnight-event-trail` | **Date**: 2026-09-18 | **Spec**: [spec.md](./spec.md)

## Summary

A new `app/transcription/event_log.py` appends one JSON object per line to `transcripts\events.jsonl`, beside the queue it describes. `TranscriptionWorker._emit` — already the single funnel through which every state reaches the window — records each snapshot, and the worker's decision points record what they decided. The writer swallows every error and rotates at a size cap, so the trail can fail entirely without the queue noticing. `tools/night_report.py` reads a trail and prints the per-file summary: phases, outcome, real duration and how accurate each promise was.

## Technical Context

**Language/Version**: Python 3.11.9 (Recorder `.venv`)

**Primary Dependencies**: `json`, `time`, `pathlib`. No new dependency.

**Storage**: `%LOCALAPPDATA%\MeetingRecorder\transcripts\events.jsonl` (plus one rotated `.1`), outside OneDrive like the rest of the queue. Bounded at 8 MB per file.

**Testing**: unittest over a temporary directory: one line per entry, unserialisable values, unwritable path, rotation at the cap, reading past a truncated line. Plus an integration assertion in `tests/test_batch_tracking.py` that driving the real monitor loop leaves a readable trail of the live switches.

**Target Platform**: Windows desktop (Grabador)

**Project Type**: Desktop app (PySide6) + sibling CLI subprocess

**Performance Goals**: one small append per emission (roughly one every 10–15 s per live file) and one per decision. Open-write-close per entry: simpler and safer than holding a handle for hours, and nowhere near a bottleneck at this rate.

**Constraints**: never raise, never block the queue, never be read by logic, never contain transcript text.

**Scale/Scope**: one new module, one new reader script, hooks at the existing decision points.

## Constitution Check

- I. Recording Always Wins — PASS (the trail records suspensions; it never delays them)
- II. Privacy Is Local — PASS (stays in `%LOCALAPPDATA%`, holds states and decisions, never transcribed content)
- III. Transcription stays a sibling subprocess — PASS (the engine is untouched; this records the Recorder's side)
- IV. Robust paths and processes — PASS (every write guarded; a failure degrades to "no trail")
- V. Simplicity — PASS (append a line; no database, no rotation policy beyond one spare file)
- Verification & Quality — PASS (the failure modes are the tests: unwritable, unserialisable, truncated, oversized)

## Design decisions

1. **Hook `_emit`, not the window.** Every state the user sees passes through `_emit`; the window only renders it. Recording there catches everything, including runs where the window is never looked at, and keeps the UI free of diagnostics.
2. **One JSON object per line.** Readable by eye, appendable without rewriting, and a half-written last line costs exactly that line.
3. **Open, write, close, per entry.** A handle held for hours across suspensions and app closes is a liability; a few thousand opens over a night is not a cost worth optimising.
4. **Rotate instead of trimming.** At the cap, the current file becomes `.1` (replacing the previous one) and a new one starts: the most recent history always survives, with no rewriting of a large file.
5. **The summary is the interface.** `tools/night_report.py` answers the questions the trail exists for — what happened per file, and how wrong the promises were — so nobody has to read raw lines.
6. **Always on.** A diagnostic that must be enabled beforehand is never on when it is needed. It is bounded and cheap, so there is no switch to forget.

## Project Structure

```text
specs/026-overnight-event-trail/
├── spec.md
├── plan.md
├── tasks.md
└── checklists/requirements.md

app/transcription/event_log.py   # append one line, never raise, rotate at the cap
app/transcription/worker.py      # hooks: run start, live switch, ready, pause/resume, degrade, fail, settle, speed
tools/night_report.py            # per-file summary of a trail
tests/test_event_log.py          # the failure modes and the reading
tests/test_batch_tracking.py     # the trail of a real monitor run
CLAUDE.md                        # where the trail lives and how to read it
```

**Structure Decision**: a module of its own rather than a few lines inside the worker, because the guarantees (never raise, bounded, readable after truncation) are worth testing in isolation from the queue.

## Complexity Tracking

> No constitution violations; section intentionally empty.
