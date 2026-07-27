<!--
Sync Impact Report
- Version change: (template) → 1.0.0
- Modified principles: placeholders → five concrete principles (see below)
- Added sections: Product Constraints; Verification & Quality
- Removed sections: none (template slots filled)
- Templates requiring updates:
  - .specify/templates/plan-template.md — ✅ no constitution-specific section changes needed
  - .specify/templates/spec-template.md — ✅ aligned (tech-agnostic specs remain)
  - .specify/templates/tasks-template.md — ✅ no new mandatory task categories
  - .claude/skills/speckit-* — ✅ no outdated governance refs to fix
- Follow-up TODOs: none
-->

# Grabador de Reuniones Constitution

## Core Principles

### I. Recording Always Wins

An active or imminent recording MUST take absolute priority over every background
task (transcription, preview refresh, device enumeration, analytics). Background
work MUST NOT start while recording is active, and MUST yield CPU (suspend or
equivalent) if a recording begins mid-job. Rationale: a missed meeting capture is
irrecoverable; a delayed transcript is not.

### II. Privacy Is Local by Default

Audio and video MUST be processed on the user's machine. Cloud upload of
meeting media is forbidden unless the user explicitly opts into a future,
separately specified feature. Integrating LLM/minuta models is out of scope
unless the constitution is amended. Rationale: meetings are confidential; the
product promise is local processing.

### III. Transcription Stays a Sibling Subprocess

Transcription MUST remain a separate project/process with its own environment
(not a fused library or shared venv). Success MUST be decided by exit status
plus output artifacts; progress logs are cosmetic. The queue MUST be durable so
jobs survive app close. Rationale: torch/pyannote churn must not break the
recorder; longevity of long jobs matters more than in-process convenience.

### IV. Paths and Processes Must Be Robust

Subprocesses MUST use argument lists (never shell string concatenation). Working
queues, logs, and temp media that would suffer under cloud sync MUST live outside
synced folders (e.g. local app data). Rationale: the app lives in paths with
spaces and OneDrive; fragile process launching already caused real failures.

### V. Simplicity for a Single Power User

Prefer the smallest design that solves a real pain for one primary user.
Scheduled-task workers, unified mega-venvs, and speculative platforms MUST NOT
be introduced without an explicit constitution amendment. Rationale: discarded
alternatives already proved over-engineered for this scale.

## Product Constraints

- Primary platform is Windows desktop; macOS/Linux remain roadmap, not blockers
  for Windows features.
- Capture quality targets: screen/window video that stays in sync with audio at
  the configured frame rate on large monitors (GPU capture preferred over
  CPU-bound fallbacks when those fallbacks miss the rate).
- The sibling Transcriptor project is the only supported transcription engine;
  the recorder integrates via CLI + durable queue, not by vendoring models.
- User-visible track names and “mix” semantics MUST remain correct for
  transcription (never feed multi-track MP4 blindly to a converter that picks
  the wrong stream).

## Verification & Quality

- Non-trivial changes that touch recording or transcription MUST be verifiable
  with the project's existing smoke/verify scripts (or an equivalent automated
  check added in the same change).
- Headless UI checks MUST avoid opening real audio devices unless the test
  explicitly requires them.
- Specs and plans MUST respect these principles; if a plan conflicts, change the
  plan or amend this constitution—do not silently violate it.

## Governance

This constitution supersedes ad-hoc implementation preferences. Amendments
require: (1) documented rationale, (2) version bump
(MAJOR = remove/redefine a principle; MINOR = add/expand; PATCH = clarify),
(3) update of dependent Spec Kit artifacts if principles change compliance
checks. All feature specs and plans MUST pass a Constitution Check against the
principles above. Runtime development guidance lives in `CLAUDE.md` and the
README; those files MUST NOT contradict this constitution—if they diverge,
amend one of them explicitly.

**Version**: 1.0.0 | **Ratified**: 2026-07-27 | **Last Amended**: 2026-07-27
