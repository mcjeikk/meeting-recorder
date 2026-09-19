# Specification Analysis Report: 021-weighted-progress-eta

**Date**: 2026-09-18 | **Artifacts**: spec.md, plan.md, tasks.md, research.md, data-model.md, contracts/progress-estimate.md | **Constitution**: v1.0.0

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| G1 | Inconsistency | HIGH (resolved during implementation) | data-model.md INV-4; spec SC-004; `eta.weighted_progress` | The first draft said "unknown duration ⇒ no percentage", and the implementation initially carried the *previous* percentage in that branch — which resurrects exactly the frozen-90% defect spec 020 fixed. | Fixed: with unknown duration the model returns the engine's raw transcription percentage and `None` during speaker identification (indeterminate), never the previous value. Covered by `tests/test_eta.py::test_unknown_duration_keeps_the_raw_percent_and_no_eta` and `tests/test_batch_tracking.py::test_unknown_duration_keeps_progress_indeterminate`. |
| G2 | Underspecification | MEDIUM (resolved) | contracts E-4/E-5; `weighted_progress` | Capping at 99 while extending the estimate made the bar converge to 95 and sit there — the same stall in a milder form. | Fixed: the stretch margin shrinks as the job runs over, so the bar creeps 95 → 99 and the remaining time grows proportionally. Asserted in `test_caps_at_99_until_the_transcript_exists`. |
| G3 | Coverage Gap | MEDIUM (resolved) | spec SC-002; tasks T018 | "Progress advances at least every 2 minutes" could not hold: emissions were driven by log lines only, and speaker identification prints nothing for hours. | Fixed: `PROGRESS_EMIT_SECONDS = 15` forces a refresh of bar and finish time every 15 s while running. |
| G4 | Ambiguity | LOW | research R3 `_asr_share` | The share of the bar covered by transcription (0.45) is a judgement call, not a measurement: the log has no per-line timestamps, so the real phase split is unobservable. It only acts as a floor, so it cannot stall or reverse the bar. | Accepted and documented in code and research. Revisit only if the bar visibly jumps. |
| G5 | Scope note | LOW | spec Assumptions; tasks Phase 5 | Correcting stale documentation (`CLAUDE.md`, preset hint, README) is inside this feature because those numbers are what a user compares the estimate against. | Done (T021–T023). |
| G7 | Inconsistency | HIGH (resolved) | data-model.md store path; `worker.__init__`; `SpeedStore.record` | The worker opened the history at the machine's real path, so the test suite (and `verify_transcription.py`, which uses a temporary queue) wrote samples into the user's own `speed.json` — with fake jobs whose active time was milliseconds, poisoning the factor to 0.00× and reducing every estimate to "1 min". Caught by running the quickstart sanity check against the real store. | Fixed twice over: the history now lives beside its queue (`store.base / "speed.json"`, so a temporary queue is isolated), and `record()` rejects implausible measurements (active < 30 s, or a factor outside 0.1–8×). The polluted file was deleted; a fresh check reads 1 h of audio → 67 min at 1.10×. Covered by `test_impossible_measurements_are_ignored`. |
| G6 | Constitution watch | LOW | contracts E-1 | Estimates must never influence behavior. Verified by inspection: `eta_epoch`, `progress` and `batch_eta_epoch` are written only into the UI snapshot; no scheduling, retry, cancel or process path reads them. | Keep E-1 in mind for future edits. |

No CRITICAL findings. No duplicated requirements. No unresolved placeholders.

## Coverage Summary

| Requirement | Has Task? | Task IDs |
|-------------|-----------|----------|
| FR-001 finish time for the file in progress | Yes | T002–T006, T011, T014 |
| FR-002 progress accounts for every phase | Yes | T005, T019 |
| FR-003 monotonic, resets on file switch | Yes | T005, T020 |
| FR-004 unknown duration ⇒ no invented estimate | Yes | T005, T009 |
| FR-005 frozen while paused | Yes | T010, T014 |
| FR-006 batch total in the summary | Yes | T012, T015 |
| FR-007 estimate revised, never in the past | Yes | T005, T006, T008 |
| FR-008 learned per configuration, persisted locally | Yes | T003, T004, T013 |
| FR-009 rounded finish time with explicit day | Yes | T006, T008 |
| FR-010 both percentage and finish time in the notice | Yes | T014, T019 |
| FR-011 corrected documentation | Yes | T021, T022, T023 |
| SC-001 ±25% accuracy for files > 10 min | Partial | T025 (needs a real run; the model uses the measured 1.05–1.23 band) |
| SC-002 advances at least every 2 minutes | Yes | T011 (15 s refresh), T018 |
| SC-003 monotonic progress | Yes | T016 |
| SC-004 no estimate without duration | Yes | T009, T016 |
| SC-005 answerable from the notice alone | Yes | T014, T015 (+T025 to confirm in use) |
| SC-006 automated coverage of the model | Yes | T007–T009, T016–T018 |
| SC-007 own median after three samples, survives restart | Yes | T007 |
| SC-008 5-minute rounding, explicit day, never past | Yes | T008 |

## Constitution Alignment

No violations.

- **I. Recording Always Wins** — active-time accounting is the mechanism that keeps a recording pause from corrupting the estimate; nothing in the estimate can start, resume or prioritize work.
- **II. Privacy Is Local** — `speed.json` stores only durations and elapsed seconds in local app data.
- **III. Sibling subprocess** — no engine change; completion is still artifact-based (the bar cannot reach 100 by time).
- **IV. Robust paths** — no new subprocess; duration from file size; history beside the queue, outside OneDrive.
- **V. Simplicity** — one pure module plus a small JSON; phase-weight modelling was explicitly rejected as guesswork.

## Unmapped Tasks

None.

## Metrics

- Total requirements: 11 FR + 8 SC = 19
- Total tasks: 25 (24 done, 1 pending a real run)
- Coverage: 19/19 have at least one task (100%); 1 partial (SC-001, needs a real run to measure)
- Ambiguity count: 1 (LOW, accepted: `_asr_share`)
- Duplication count: 0
- Critical issues: 0
- Suite: 153 tests green (was 122 before the audit, 131 after 020)

## Next Actions

1. Nothing blocking. T025 (real-run acceptance) is the only open item, together with 020's T030 — both need the app restarted.
2. When the next long batch finishes, compare the shown finish time against reality; the learned factor should then replace the default for that configuration.
3. Proceed to the remaining audit features: 022 (usable quick verification) and 023 (queue history pruning).
