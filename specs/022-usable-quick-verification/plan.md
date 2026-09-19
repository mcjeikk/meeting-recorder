# Implementation Plan: A quick check that can actually be run

**Branch**: `022-usable-quick-verification` | **Date**: 2026-09-18 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/022-usable-quick-verification/spec.md`

## Summary

`verify_transcription.py` already drives the real path (real `JobStore`, real `TranscriptionWorker`, real engine subprocess) with a temporary queue — that part stays. What changes: `--quick` stops meaning "the whole recording without speakers" and starts meaning "a short slice of a real recording into a throwaway destination". The slice is cut with `ffmpeg -t N -map 0 -c copy`, which keeps the meeting's multi-track layout so the "Mezcla" selection is genuinely exercised, and takes about a second. Destination, queue and speed history all live under one temporary folder, so a run can never touch the user's transcripts or learned factors. The verdict now also requires that progress updates and a finish-time estimate arrived (specs 020/021), and that speakers were really produced when requested. The decisions the script makes are extracted into importable functions so they can be unit-tested without the engine.

## Technical Context

**Language/Version**: Python 3.11.9 (Recorder `.venv`)

**Primary Dependencies**: Existing `JobStore` / `TranscriptionWorker` / `integration` helpers; bundled ffmpeg via `app/encode/ffmpeg.get_ffmpeg_exe` for the slice. No new dependency. Sibling engine unchanged.

**Storage**: Everything under one temp folder per run (`verify_tx_*`): `queue/`, `logs/`, `work/`, `speed.json` and the destination `Transcripciones/`. Deleted on success, kept on failure.

**Testing**: unittest for the pure decisions (`tests/test_verify_quick.py`): destination isolation, slice arguments, verdict rules (missing artifacts, no progress updates, speakers dropped), sample shorter than requested. The engine run itself is validated by running the script manually (quickstart).

**Target Platform**: Windows desktop (Grabador)

**Project Type**: Desktop app (PySide6) + sibling CLI subprocess; this feature is a maintenance script

**Performance Goals**: fast variant under 2 minutes, default (with speakers) under 5, on the audited laptop; slice extraction about 1 s.

**Constraints**: Argument lists, never `shell=True` (paths with spaces / OneDrive); must not read or write the user's configuration beyond reading where recordings live; must leave no child process behind; must not require flags whose misuse destroys data.

**Scale/Scope**: One developer machine; one recording sampled per run.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- I. Recording Always Wins — PASS (the check runs a normal queued job; the worker's own recording guard applies unchanged, and the script never starts while claiming priority)
- II. Privacy Is Local — PASS (a slice of local media into a temp folder, deleted afterwards; nothing leaves the machine)
- III. Transcription stays a sibling subprocess — PASS (this is precisely the contract the script verifies: subprocess + artifacts decide success)
- IV. Robust paths and processes — PASS (argument lists for ffmpeg and the engine; temp folders outside OneDrive; interruption reports the child instead of orphaning it silently)
- V. Simplicity — PASS (one script, one temp folder, no new infrastructure)
- Verification & Quality — PASS (this feature *is* the verification requirement; it also makes the constitution's "verifiable with the project's own scripts" rule satisfiable again)

Post-design re-check: unchanged. Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/022-usable-quick-verification/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/verify-cli.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
verify_transcription.py             # rewritten: sample slice, isolated destination, richer verdict, clear exit codes
app/transcription/integration.py    # (read-only use) track selection + extraction already exercised
CLAUDE.md                           # "Verificación rápida" section: the command that actually runs
README.md                           # mention the maintenance check briefly

tests/test_verify_quick.py          # NEW: destination isolation, slice args, verdict rules
```

**Structure Decision**: Keep it as one top-level script (it is a maintenance tool, not app code), but move its decisions into module-level functions so tests can import them. No new package; no changes to app behavior.

## Complexity Tracking

> No constitution violations; section intentionally empty.
