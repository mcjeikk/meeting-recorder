# Analysis: The queue forgets what it no longer needs

**Date**: 2026-09-18 · Artifacts: spec.md, plan.md, research.md, data-model.md, contracts/queue-retention.md, tasks.md, quickstart.md · Implementation: `app/transcription/retention.py`, `jobs.py`, `integration.py`, `import_media.py`, `worker.py`, `app/ui/main_window.py`, `tests/test_retention.py`, `tests/test_transcribe_any_file.py`

## Findings

| ID | Category | Severity | Location(s) | Summary | Resolution |
|----|----------|----------|-------------|---------|----------------|
| G1 | Underspecification | HIGH (resolved) | spec SC-002; `prune_history` | The spec asserted a pass would take "well under a second". The first test run pruned 300 synthetic records in **3.8 s** — deleting freshly written files costs ~16 ms each here (antivirus inspects every unlink). A startup that spends seconds paying off a historical backlog is not what "silent housekeeping" promised. | Fixed by design, not by relaxing the claim: FR-012 adds a per-pass budget (`MAX_DELETIONS_PER_PASS = 100`, oldest first) so one start never pays the whole debt and a backlog converges over a few starts. SC-002 now carries measured numbers. Covered by `test_three_hundred_records_are_pruned_fast` (budget honoured, oldest-first, converges, then idempotent) and `test_budget_takes_the_oldest_first`. |
| G2 | Inconsistency | MEDIUM (resolved) | data-model INV-3; contracts A-6 | "Pruning is idempotent" was false in the presence of a budget: a second pass legitimately keeps deleting until the limits are met. | Reworded to "idempotent once converged", and the test asserts both halves: successive passes converge, and a converged queue loses nothing. |
| G3 | Measurement correction | MEDIUM (resolved) | research R1; spec SC-002 | The 16 ms/unlink figure that justified the budget did not reproduce on the real queue: 80 deletions took **20 ms** total. The synthetic figure came from files created milliseconds earlier in `%TEMP%`. | Both numbers are now documented where the constant lives: the budget guards the worst case observed, not the normal one. Keeping the guard is still the right call — it costs three lines and bounds an unbounded worst case. |
| G4 | Coverage Gap | MEDIUM (resolved) | spec US2; plan Source Code | The plan put the US2 tests in a new `tests/test_import_media.py`, but the import path already has `tests/test_transcribe_any_file.py`. Two files for one module means the next person tests in one and misses the other. | The tests went into the existing file (T029), next to the record-based cases they now complement. |
| G5 | Risk accepted | LOW | `transcript_exists`; INV-10 | The disk check resolves the destination from the *current* configured output folder. A file transcribed while a different output folder was configured will not be recognised once its record is pruned, and would be transcribed again. | Accepted: the record covers the recent case (30 days), and the alternative — scanning every folder the user has ever configured — is not knowable. Documented as INV-10's sibling case in the quickstart's "thing to remember". |
| G6 | Constitution watch | LOW | FR-006; `prune_history` | Nothing outside `queue/` and `logs/` may be touched. Verified by inspection: the only writes are `unlink` on paths derived from `self._path(job_id)` and `self.logs_dir.glob("*.log")`. The learned speed history (spec 021) lives in the same folder but is never globbed (`*.log` / `<id>.json` only). | Keep in mind: a future `*.json` glob over `base` would eat `speed.json`. |

No CRITICAL findings. No duplicated requirements. No unresolved placeholders.

## Coverage Summary

| Requirement | Covered by | Status |
|-------------|------------|--------|
| FR-001 remove finished records past 30 days | T004, T012; `prunable_job_ids` | Done |
| FR-002 cap at ~200 newest | T004; `max_history` | Done |
| FR-003 never prune live/failed/cancelled | T008; `prunable_job_ids` filters to `done` | Done |
| FR-004 prune their logs and orphan logs | T005, T022; `prunable_log_paths` | Done |
| FR-005 automatic, silent, at startup | T013; `_reconcile` call, no emission | Done |
| FR-006 touch nothing else | G6 inspection; `prune_history` only unlinks in `queue/`, `logs/` | Done |
| FR-007 disk answers "already transcribed" | T017–T018; `transcript_exists` | Done |
| FR-008 recognised file is not queued, reported as today | T014, T016; wording unchanged | Done |
| FR-009 survive corrupt data and locked files | T009, T021; guarded unlinks, `job_age_key` never raises | Done |
| FR-010 limits in one place | `retention.py` constants | Done |
| FR-011 documentation | T023–T025; CLAUDE.md, README.md, quickstart.md | Done |
| FR-012 bounded work per pass | T028; `oldest_first` + budget | Done |
| SC-001 300 records converge to the limits | `test_three_hundred_records_are_pruned_fast` | Met |
| SC-002 no perceptible startup cost | real queue: 33+47 deletions in 20 ms; converged pass 3 ms | Met |
| SC-003 live/failed records and logs untouched | `test_prune_removes_records_and_their_logs`, `test_live_and_failed_records_are_never_prunable` | Met |
| SC-004 pruned + transcript on disk ⇒ not re-queued | `test_pruned_record_with_transcript_is_not_re_enqueued` | Met |
| SC-005 no log outlives its record | `test_logs_of_surviving_records_are_kept`, `test_orphan_log_is_removed` | Met |
| SC-006 repeated pruning is a no-op | `test_nothing_to_do_is_silent`, `test_pruning_twice_removes_nothing_the_second_time` | Met |

## Real-queue acceptance (T027)

```text
antes:   64 registros, 68 logs        (oldest 2026-06-10)
borrado: 33 registros, 47 logs en 20 ms
despues: 31 registros, 21 logs
segunda pasada: {'records': 0, 'logs': 0} en 3 ms
pending(): 2.0 ms por consulta        (era ~4.1 ms con 64 registros)
```

Whole suite: 194 tests green. `verify_transcription.py --quick --no-speakers --seconds 20`: pass in 18 s. A backup of the pre-prune queue and logs is at `%LOCALAPPDATA%\MeetingRecorder\transcripts_backup_2026-09-18`.

## Constitution Alignment

All five principles pass, as in the plan. Worth restating one: pruning runs on the worker thread, which is also where the recording gate lives, so housekeeping can never contend with a recording.

## Notes for the next feature

- `JobStore.all()` is still O(records) per question, now with a bounded n. If the queue ever needs to grow (batch imports of hundreds of files), an index — not a bigger cap — is the answer.
- The stage label carried over from spec 022's analysis (`Audio listo… 35%` while transcribing) is still unaddressed and is the most visible remaining cosmetic defect.
