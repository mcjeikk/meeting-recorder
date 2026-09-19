# Specification Analysis Report: 020-batch-queue-tracking

**Date**: 2026-09-18 | **Artifacts**: spec.md, plan.md, tasks.md, research.md, data-model.md, contracts/cli-progress-log.md | **Constitution**: v1.0.0

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| F1 | Inconsistency | MEDIUM | spec.md Edge Cases (pid reuse); data-model.md "cohort"; `worker._cohort` | The cohort is grouped by shared child pid over the whole queue. Terminal jobs keep their pid in existing queue files (59 of 64 on the audited machine, 10 of them sharing pid 20708), so a reused pid can attach historical jobs to a live batch and inflate `batch_total` ("archivo 1 de 11"). T024 only prevents this for jobs finished from now on. | Restrict cohort grouping to non-terminal jobs (plus the seed). Add task. |
| F2 | Coverage Gap | MEDIUM | spec.md SC-003; tasks.md T008 | "The notice never names a file whose transcript already exists" is only covered indirectly (the test asserts the last active emission is the next file). No assertion states that no emission with `status=running` names an already-finished file. | Add an explicit assertion to `tests/test_batch_tracking.py`. Add task. |
| F3 | Underspecification | LOW | spec.md Assumptions; plan.md; `worker._batch_position` | Batch position assumes the engine processes files strictly in argv order. True today (the CLI loops over `args.entrada`), but the display would silently mislead if that ever changed. | Keep as documented assumption; the contract file already pins the log lines this depends on. No task. |
| F4 | Ambiguity | LOW | spec.md FR-004 ("indeterminate") | "Indeterminate" is a UI concept; the spec deliberately avoids naming the widget. Acceptance scenario 4 makes it testable ("progress is shown as indeterminate and the stage is named"), so this is acceptable phrasing, not a defect. | No action. |
| F5 | Scope note | LOW | spec.md Assumptions; research.md R8 | Weighted progress/ETA, queue pruning and the smoke-test fix are excluded here and tracked as separate features. Tasks and success criteria stay inside the stated scope. | No action. |

No CRITICAL or HIGH findings. No duplicated requirements. No unresolved placeholders.

## Coverage Summary

| Requirement | Has Task? | Task IDs |
|-------------|-----------|----------|
| FR-001 one file in progress | Yes | T009, T014, T015, T016 |
| FR-002 engine is the source of truth | Yes | T002, T003, T005, T011 |
| FR-003 ready as soon as the transcript exists | Yes | T010 |
| FR-004 percentage belongs to the live file | Yes | T002, T012 |
| FR-005 notice names the live file + position | Yes | T013, T016 |
| FR-006 truthful summary counts | Yes | T014, T016 |
| FR-007 per-file failure attribution | Yes | T004, T020 |
| FR-008 never-started returns to queue; readable reasons | Yes | T011, T023 |
| FR-009 cancelled not resurrected; cancel of a waiting file | Yes | T021, T022 |
| FR-010 per-file notification during a batch | Yes | T017 |
| FR-011 no stale import hint while running | Yes | T016 |
| FR-012 reclaim intermediate audio | Yes | T026, T027 |
| FR-013 selection does not hijack the notice | Yes | T016 |
| SC-001 one in progress; ready count matches disk | Yes | T007, T008 |
| SC-002 ready within one refresh | Yes | T008, T010 |
| SC-003 notice never names a finished file | Partial | T008 (indirect) → F2 |
| SC-004 one failure costs only that file | Yes | T018 |
| SC-005 zero leftover intermediate audio | Yes | T025 |
| SC-006 tests drive the real monitoring loop | Yes | T006, T007, T008, T018, T019, T025 |

## Constitution Alignment

No violations. Checked explicitly:

- **I. Recording Always Wins** — the pause/suspend branch is preserved and keeps naming the live file; tracking adds no work while recording.
- **III. Transcription stays a sibling subprocess** — no Transcriptor change; success remains artifact-based (`transcripcion.txt`), and the log is used only for progress and for *attributing* failures, never to declare success.
- **IV. Robust paths** — name-based matching (no path comparison), argument lists untouched, queue/logs/work stay in `%LOCALAPPDATA%`.
- **V. Simplicity** — one dependency-free parsing module, no new process or persisted state.
- **Verification & Quality** — the previously untested monitoring loop is now driven by automated tests (SC-006).

## Unmapped Tasks

None. T029 (full suite) and T030 (manual acceptance on a real batch) are verification tasks tied to SC-006 and the quickstart, not orphans.

## Metrics

- Total requirements: 13 FR + 6 SC = 19
- Total tasks: 30 (29 done, 1 pending user run)
- Coverage: 19/19 have at least one task (100%); 1 partial (SC-003)
- Ambiguity count: 1 (LOW, accepted)
- Duplication count: 0
- Critical issues: 0

## Next Actions

1. Remediate F1 and F2 (small, inside this feature's scope) → new tasks T031, T032.
2. Re-run the suite.
3. T030 stays open until the next real multi-file batch runs after an app restart.
