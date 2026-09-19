# Analysis: spec ↔ plan ↔ tasks ↔ code (spec 025)

**Date**: 2026-09-18 · Non-destructive cross-check after implementation.

## Coverage

| Requirement | Where it lives | Verified by |
|---|---|---|
| FR-001 load charged at most once per run | `eta.estimate_total_seconds(..., load_models=)` | `test_the_first_file_of_a_run_pays_the_load`, `test_batch_estimate_carries_one_model_load_not_one_per_file` |
| FR-002 a file reusing models is not charged | `worker._monitor` (three `tracker.reset` sites) | `test_a_file_that_reuses_the_models_only_pays_its_audio`, `test_reset_forwards_who_pays_the_model_load`, `test_a_file_promoted_inside_a_running_engine_pays_no_model_load` |
| FR-003 batch adds work only | `worker._batch_eta` | `test_batch_estimate_carries_one_model_load_not_one_per_file` |
| FR-004 measured charge, one place | `eta.STARTUP_SECONDS` = 12 s with the method in the comment | `test_the_charge_is_the_measured_one`, `CLAUDE.md`, research.md |
| FR-005 spec 021 guarantees intact | unchanged `weighted_progress` | the whole existing `TestWeightedProgress` class, plus the real runs below |
| FR-006 speed samples stay comparable | **no code change** — see Findings | reasoned, not enforced |
| FR-007 estimate stays advisory | unchanged: no caller reads it for decisions | grep of `eta_epoch` / `batch_eta` consumers: UI text only |
| FR-008 engine untouched | no file under `..\Transcriptor` modified | `git status` |

## Measured outcome

Same script, same two recordings, same configuration, before and after the change:

| Criterion | Before | After |
|---|---|---|
| SC-003 · 300 s samples within 15 % | +57 s (+18 %) and +40 s (+12 %) — **fail** | +27 s (+8.6 %) and +10 s (+3.0 %) — **pass** |
| SC-004 · 45 s sample under twice the real time | 90 s promised vs 42 s real (2.1×) — **fail** | 62 s vs 53 s, 62 s vs 54 s, 60 s vs 46 s (1.2–1.3×) — **pass** |
| SC-005 · specs 020/021/024 criteria still hold | 8 of 9 | **9 of 9**, in both the 45 s and the 300 s runs |
| SC-006 · suite green | 207 tests | **215 tests** |

Side effect worth noting: because the estimate is tighter, the bar now travels further during speaker identification — 40 → 90 % and 41 → 94 % on the 300 s samples, against 40 → 81 % and 40 → 85 % before. The user sees more movement in the phase that used to look frozen.

The batch case was exercised end to end in the 45 s run: the notice showed "archivo 1 de 2" and "archivo 2 de 2", the first of the pair was promised 62 s (49.5 s of work plus the 12 s load) and the second was not charged the load at all.

`verify_transcription.py --quick --seconds 30`: OK in 38 s, three artifacts, one speaker, phases read `Transcribiendo… 6%` → `Identificando hablantes… 37%` → `71%` → done.

## Findings

**F1 · FR-006 is reasoned, not enforced (accepted).** A speed sample from the first file of a run silently includes ~12 s of model load; one from a later file does not. Nothing in the code separates them. Accepted because the existing minimum of 60 s of audio per sample keeps the contamination under 20 % of the smallest accepted sample and under 2 % for real meetings, and the median of three or more samples absorbs it. Recorded here so a future change does not mistake it for an oversight. Fixing it properly needs per-phase timings the engine does not print.

**F2 · The 60 s floor now dominates very short files.** `weighted_progress` never promises less than 60 s of remaining time. With the load charge down to 12 s, a 45 s sample that reuses models is estimated at 49.5 s of work but still promised 60 s — which is why the third file of the short run showed +14 s while the others showed +7 s and +8 s. Harmless for the app's purpose (meetings, where the floor is invisible, and the notice rounds to 5 minutes anyway) and out of scope here; noted because it is now the largest remaining source of error on short files.

**F3 · The constant is warm-cache and single-machine.** 12 s came from one laptop with the models already in the OS file cache. A cold start or slower storage pays more, and the first file of a run will then run long — handled by spec 021's stretch rule, which moves the promise forward instead of leaving it in the past. `quickstart.md` documents how to re-measure rather than guess.

**F4 · Both defects were invisible to the test suite before this feature.** The suite asserted the composition of the estimate against itself (`estimate_total_seconds` was both the code under test and the expected value), so a wrong constant and a wrong charge per file could not fail. What caught it was comparing against reality: two files of identical length differing only in who loaded the models. The lesson generalises to anything that estimates: at least one test has to compare against a measurement, not against the formula.

## Conclusion

No inconsistencies between spec, plan, tasks and code. Two findings accepted with reasons (F1, F2), one risk documented with its remedy (F3), one process lesson (F4). Nothing pending.
