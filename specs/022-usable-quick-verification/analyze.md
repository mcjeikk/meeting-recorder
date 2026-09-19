# Analysis: A quick check that can actually be run

**Date**: 2026-09-18 · Artifacts: spec.md, plan.md, research.md, data-model.md, contracts/verify-cli.md, tasks.md · Implementation: `verify_transcription.py`, `app/transcription/worker.py`, `tests/test_verify_quick.py`

## Findings

| ID | Category | Severity | Location(s) | Summary | Resolution |
|----|----------|----------|-------------|---------|----------------|
| G1 | Inconsistency | HIGH (resolved) | contracts Verdict §5; data-model INV-4; `speakers_in_result` | The verdict counted `hablantes` as a list or a number, but the engine writes a **map** (`{"SPEAKER_00": …}`). The first real run with speakers therefore failed a perfectly healthy pipeline: the log said "1 hablante(s) detectado(s)" and the check printed "se pidieron hablantes y el resultado no trae ninguno". A check that cries wolf is worse than no check. | Fixed: maps, lists and numbers are all counted; `test_speaker_map_is_counted` pins the real shape. Re-run: exit 0, 1 speaker, 32 s. Note the app's own `worker._check_speakers` was never affected — it tests truthiness, and a non-empty dict is truthy. |
| G2 | Inconsistency | MEDIUM (resolved) | contracts V-6; data-model INV-5; `main` cleanup | The first passing run left its sandbox behind: the worker thread still held `tx/worker.lock` open, and `shutil.rmtree(..., ignore_errors=True)` swallowed the failure silently, so SC-003 ("no temporary folder left behind") failed while the script claimed success. | Fixed: `TranscriptionWorker.shutdown(wait=)` joins the thread and closes the lock **only if the thread really stopped**, then `cleanup_sandbox` retries the delete and says so if it still cannot. Verified: `$env:TEMP\verify_tx_*` is empty after a pass. |
| G3 | Ambiguity | LOW | spec Edge Cases; contracts V-3 | "A source shorter than the request is used whole" is delegated to ffmpeg (`-t` beyond the end simply stops at the end) rather than measured and clamped in the script. | Accepted: no extra probe call, and the behavior is exactly what the requirement asks. The unit test asserts the argument shape; the real clamp is ffmpeg's. |
| G4 | Coverage note | LOW | spec SC-002; quickstart | SC-002 budgets 5 minutes for the default 60 s sample; the measured runs used a 20 s sample (22 s / 32 s). The default was not timed end to end. | Accepted: the sample length is linear in the engine's work and the 20 s runs sit an order of magnitude under budget. `quickstart.md` states which variant was measured instead of implying the default was. |
| G5 | Scope note | LOW | plan Source Code; `worker.shutdown` | The feature is a maintenance script, yet it required a small change in app code (releasing the queue lock on shutdown). | Accepted and intentional: releasing your own lock when you stop is correct behavior for the app too, and it is guarded so a worker still following a child never releases it. |
| G6 | Constitution watch | LOW | contracts V-7; Principle III | The check must never reconfigure the engine. Verified by inspection: it only reads `cfg.transcriptor_dir` through `integration.is_available` and invokes the CLI through the app's own command builder. | Keep V-7 in mind if the check ever needs to force a model or a token. |

No CRITICAL findings. No duplicated requirements. No unresolved placeholders.

## Coverage Summary

| Requirement | Covered by | Status |
|-------------|------------|--------|
| FR-001 sample instead of whole file, adjustable | T010; `slice_args`, `--seconds` | Done |
| FR-002 throwaway queue, destination and history | T003; `sandbox_paths`, `SpeedStore(store.base/…)` (spec 021 T026) | Done |
| FR-003 no data-destroying flag required, never refuses | T005; `--quick` never consults the real destination | Done |
| FR-004 real path end to end | T010–T011; real `JobStore` + `TranscriptionWorker` + engine subprocess | Done |
| FR-005 verify and report artifacts | T012, T019; `verdict` | Done |
| FR-006 opt-in speaker verification | T018–T019 | Done |
| FR-007 progress + finish estimate confirmed | T021–T022 | Done |
| FR-008 clean on success, keep on failure | T014–T015; `cleanup_sandbox` | Done |
| FR-009 bounded duration, distinct exit codes | T004; `--timeout`, EXIT_* | Done |
| FR-010 full mode still available | full branch with `--force` | Done |
| FR-011 documentation describes the runnable command | T023–T025 | Done |
| SC-001 succeeds where every recording already has a transcript | manual run T027 (exit 0) | Met |
| SC-002 under 5 min (default) / 2 min (fast) | 32 s / 22 s on a 20 s sample | Met (see G4) |
| SC-003 user data untouched, no leftovers | timestamps of the real queue unchanged; `$env:TEMP` clean | Met (after G2) |
| SC-004 broken wiring reported, never a pass | T006–T009, T020; missing engine → exit 3 | Met |
| SC-005 dropped speakers = failure | T016–T017 | Met |
| SC-006 automated tests for the decisions | `tests/test_verify_quick.py` (18 tests) | Met |

## Constitution Alignment

All five principles pass, as in the plan. The feature restores the "verifiable with the project's own scripts" clause that the previous script could not satisfy.

## Notes for the next feature

- The banner stage text shows `Audio listo… 35%` while transcribing: the stage label sticks to the last line the log printed instead of naming the current phase. Cosmetic, out of scope here, worth a small spec.
- The real `speed.json` does not exist yet (it was deleted in spec 021's remediation); the first real meeting after this will recreate it with a plausible sample.
