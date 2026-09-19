# Analysis: The notice names the phase that is actually running

**Date**: 2026-09-18 · Artifacts: spec.md, plan.md, research.md, data-model.md, contracts/phase-labels.md, tasks.md, quickstart.md · Implementation: `app/transcription/cli_progress.py`, `app/transcription/worker.py`, `tests/test_cli_progress.py`, `tests/test_batch_tracking.py`

## Findings

| ID | Category | Severity | Location(s) | Summary | Resolution |
|----|----------|----------|-------------|---------|----------------|
| G1 | Root cause confirmed | HIGH (resolved) | `parse_plain_chunk`; Transcriptor `procesar_archivo` | The engine's transcription announcement (`- Transcribiendo (modelo …)`) was never matched, so the label kept `Audio listo…` — the note that the WAV needed no conversion — until a percentage line arrived. Percentages print only on jumps of ≥10 points, so the stale label could cover the whole transcription. | Fixed: the announcement sets the transcribing phase, and `Audio ya en WAV` sets none. Verified against the real engine: the same run that printed `Audio listo… 4%` now prints `Transcribiendo… 3%`. |
| G2 | Inconsistency | MEDIUM (resolved) | `-> dispositivo:` handling | `-> dispositivo: cuda` relabelled to `Transcribiendo (GPU)…`, but the engine prints that line *after* transcription returns: the label asserted a phase that had just ended, and the next announcement follows milliseconds later, so it was both wrong and practically unreachable. | Fixed: the device line now marks the end of transcription (writing-results phase) and no longer relabels. The GPU fact stays in the log; a device indicator in the UI is deliberately out of scope. |
| G3 | Hidden coupling | HIGH (resolved) | `worker._monitor` | Progress behavior was keyed on display text: `"hablantes" in nuevo_stage.lower()` decided that the engine's percentage did not apply. Rewording the notice would silently change how the bar behaves — the same class of coupling behind the frozen-90% defect. | Fixed: `parse_plain_chunk` returns an explicit phase, and the worker compares it against `PHASES_WITHOUT_ASR_PERCENT`. Asserted end to end in `test_phase_drives_the_label_and_the_percent`, which checks the label sequence *and* that the stale 40% stops applying — without the word `hablantes` appearing in the log it feeds. |
| G4 | Coverage Gap | MEDIUM (resolved) | spec SC-001 | The phase sequence was only observable through a real engine run, which the suite cannot do. | Fixed: `LOG_REAL` in `tests/test_cli_progress.py` is the verbatim log of a finished job, replayed line by line, asserting prepare → asr → speakers → saving. |
| G5 | Observation | LOW | spec Assumptions; quickstart | `Guardando resultados…` did not appear in the 20 s acceptance run: the job completed between two polls. The label is correct but, on short files, invisible. | Accepted and documented: the phase exists for the gap on real meetings, where merging and writing take longer than a poll. The unit tests cover the label directly, so its absence in a fast run is not a coverage hole. |
| G6 | Constitution watch | LOW | contracts W-4; Principle I | The pause label (`⏸ En pausa (grabando)…`) is emitted by the worker and must keep precedence over any phase label. Verified by inspection: it is emitted in its own branch and does not consult the phase. | Keep W-4 in mind if phases ever gain their own emission path. |

No CRITICAL findings. No duplicated requirements. No unresolved placeholders.

## Coverage Summary

| Requirement | Covered by | Status |
|-------------|------------|--------|
| FR-001 label from the engine's announcements | T010; `_RE_ASR_START` | Done |
| FR-002 no preparation label during transcription | T011; `test_preparation_label_never_carries_an_asr_percent` | Done |
| FR-003 never claim a finished phase | T012; `test_device_line_means_transcription_ended` | Done |
| FR-004 truthful label for the final stretch | T012; `PHASE_SAVING` | Done |
| FR-005 speakers keep their label and indeterminate percentage | T013; `test_diarization_clears_asr_percent` | Done |
| FR-006 phase as a value, decisions keyed on it | T003, T016; `PHASES_WITHOUT_ASR_PERCENT` | Done |
| FR-007 unknown lines change nothing | T008; `test_unknown_lines_change_nothing` | Done |
| FR-008 device does not drive the label | T012 | Done |
| FR-009 existing behavior preserved | full suite, 206 tests green | Done |
| FR-010 engine untouched | no file changed under `Transcriptor/` | Done |
| SC-001 real-log replay gives the right sequence | `test_real_log_replayed_line_by_line` | Met |
| SC-002 never preparation + transcription percentage | `test_audio_already_wav_is_not_a_phase`, real run | Met |
| SC-003 short file still says transcribing | `test_announcement_alone_says_transcribing` | Met |
| SC-004 no decision from label words | `worker._monitor` phase check; grep finds none | Met |
| SC-005 existing tests unchanged in behavior | 206 green, including batch tracking and ETA | Met |
| SC-006 wording lives in one place | `PHASE_LABELS` + `label_for_phase`; `test_every_phase_has_exactly_one_label` | Met |

## Acceptance evidence (T021)

```text
[20:33:36] extracting Preparando audio…
[20:33:36] running    Transcribiendo… 0%
[20:33:38] running    Transcribiendo… 3%          ← antes: "Audio listo… 4%"
[20:33:52] running    Identificando hablantes… (la fase más lenta) 25%
[20:34:07] running    Identificando hablantes… (la fase más lenta) 50%
[20:34:08] done       Listo 100%
OK en 34s — cableado completo verificado · Hablantes: 1
```

Whole suite: 206 tests green.

## Constitution Alignment

All five principles pass, as in the plan. Principle III is worth restating: this feature reads *more* of the engine's existing output and changes nothing in the sibling project.

## Notes for the next feature

- The engine prints nothing between `- Identificando hablantes` and its result, which is the longest phase of a real meeting. Spec 021's time-based bar covers it; a finer-grained signal would require changing the engine (out of scope by Principle III).
- With this, every item the 2026-09-18 audit raised is either shipped (020–024) or explicitly deferred with a reason: an index for `JobStore` (only if batch imports grow), a GPU/CPU indicator in the UI, and the manual acceptance runs that only the user can sign off (020 T030, 021 T025).
