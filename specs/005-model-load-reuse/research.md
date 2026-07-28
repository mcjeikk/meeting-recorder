# Research: Model-Load Reuse

## R1 — Where does cold-start cost live?

**Decision**: Cost is inside the Transcriptor process (Whisper/CTranslate2 model load + optional pyannote). Recorder only pays process spawn + WAV extract.

**Rationale**: Architecture is one CLI invocation per queue job; stdout to log file.

## R2 — What reuse is constitution-legal?

**Decision**: Only a **sibling** long-lived process (or future batch mode inside one Transcriptor invocation). Never import models into Recorder.

**Evidence**: Constitution III; CLAUDE.md discarded unified venv; CTranslate2 docs encourage load-once reuse in-process.

## R3 — Smallest useful slice this pass?

**Decision**: **None.** An unused `--keep-alive` flag or incomplete socket server is negative value. Docs + deferral beat half-broken daemon.

**Alternatives considered**:
- CLI keep-alive waiting on stdin for next path — needs Recorder protocol rewrite + crash handling.
- Prefetch/warmup subprocess discarded after first job — wastes RAM and fights Recording Always Wins.
- Accept cold start (002 option C) — chosen for this pass.

## R4 — When to revisit

Revisit when measured model-init dominates wall time for the user’s typical preset **and** there is appetite for a small IPC contract + integration tests. Until then, presets (Rápido) remain the user-facing speed lever.
