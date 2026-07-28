# Feature Specification: Model-Load Reuse (Phase 2)

**Feature Branch**: `005-model-load-reuse`

**Created**: 2026-07-28

**Status**: Deferred (plan ready; code not shipping)

**Input**: User description: "Daemon / model-load reuse (002 Phase 2) — constitution-compliant MVP only if safe; else scoped Phase 2 plan update + smallest useful slice OR skip with explicit rationale. Prefer shipping value over a half-broken daemon. Transcription stays sibling subprocess; NO fused venv; Recording Always Wins."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Honest reuse plan without breaking recording (Priority: P1)

As the user, I want successive transcriptions with the same quality settings to eventually avoid paying full model-load cost every time, but only if that can be done without merging Transcriptor into the Recorder process and without stealing CPU/GPU from an active recording.

**Why this priority**: Model cold-start is real on CPU-only machines; a wrong daemon design would violate constitution III/I or leave a half-broken long-lived process.

**Independent Test**: Feature artifacts document at least one constitution-compliant approach, measurement steps, and an explicit ship/defer decision. No Recorder import of torch/faster-whisper.

**Acceptance Scenarios**:

1. **Given** Phase 1 presets already ship, **When** planners review Phase 2, **Then** the plan keeps transcription as a separate process/environment and Recording Always Wins intact.
2. **Given** a full warm daemon is judged too large/risky for this pass, **When** the feature closes, **Then** a short deferral note states why and what would be required later — without claiming reuse is live in the product.

---

### User Story 2 - Optional smallest useful Transcriptor slice (Priority: P3)

If a tiny, opt-in Transcriptor-side improvement can land without changing Recorder’s one-job-per-process contract, it MAY ship; otherwise it MUST be skipped rather than half-wired.

**Why this priority**: Prefer value over ceremony; a keep-alive CLI flag unused by Recorder adds surface area without user benefit.

**Independent Test**: Either (a) no Transcriptor code change with documented rationale, or (b) an opt-in CLI path that does not alter default one-shot behavior and is not required by Recorder.

**Acceptance Scenarios**:

1. **Given** default `transcribe.py` invocation, **When** Recorder runs a job as today, **Then** behavior is unchanged (exit code + artifacts).
2. **Given** no safe slice fits this pass, **When** implement is skipped, **Then** tasks mark code work deferred and multi-monitor / preview / mute backlog proceeds.

### Edge Cases

- Warm process dies mid-queue → Recorder must fall back to cold one-shot without losing durable queue jobs.
- Recording starts while sibling is warm → Recording Always Wins still refuses new jobs / suspends child.
- Preset change between jobs → warm cache must invalidate or reload matching model settings.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Any reuse design MUST keep transcription in the sibling Transcriptor environment (separate venv/process); Recorder MUST NOT import ASR/diarization stacks.
- **FR-002**: Recording Always Wins MUST remain: no job spawn while recording when configured; suspend/resume of sibling child still applies.
- **FR-003**: Phase 2 MUST NOT block shipping other audit items; if full daemon is out of scope, artifacts MUST record deferral rationale.
- **FR-004**: If code ships, default CLI one-shot behavior MUST remain identical for existing Recorder `build_command` invocations.
- **FR-005**: Success measurement (when implemented) MUST compare cold vs warm second same-preset job model-init wall time on one machine.

### Key Entities

- **ReuseApproach**: Documented option (long-lived sibling worker vs accept cold start).
- **DeferralNote**: Explicit decision for this implement pass.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Spec + plan + tasks exist under `specs/005-model-load-reuse/` with a clear ship/defer verdict.
- **SC-002**: Constitution III and I are cited as pass/fail gates for any proposed code.
- **SC-003**: Product README / UX do not claim model reuse is live unless code ships.
- **SC-004**: If deferred, remaining audit features (multi-monitor, preview, mute) are unblocked the same day.

## Assumptions

- One power user; cold start per job remains acceptable until a measured warm path exists.
- Presets (002) already encode model/beam/diarize; reuse would key off those settings.
- No Windows Scheduled Task mega-worker (constitution V).
