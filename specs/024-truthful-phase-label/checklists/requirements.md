# Requirements Checklist: The notice names the phase that is actually running

Gate applied to `spec.md` before planning.

## Clarity

- [x] The defect is stated with the observed output (`Audio listo… 4%`, `Audio listo… 35%`) and what the engine was doing at that moment
- [x] Requirements describe what the user reads, not regexes or function names
- [x] "Truthful" is pinned down: never a phase the engine reported finished, never preparation next to a transcription percentage
- [x] No placeholders or open questions remain

## Completeness

- [x] Covers all four phases, including the previously unnamed final stretch
- [x] Covers the short-file case where no percentage is ever printed
- [x] States what must NOT change (live file, resets, notes, per-file errors, pause precedence)
- [x] States that the sibling engine is untouched

## Consistency

- [x] Does not contradict spec 020's log contract (it matches more of the same lines)
- [x] Does not contradict spec 021: the percentage still comes from elapsed time, the phase only says whether the engine's figure applies
- [x] The GPU decision is explicit rather than silently dropped

## Testability

- [x] Every criterion is checkable by replaying log text through a pure parser
- [x] SC-004 is checkable by inspection (no behavior keyed on label words)
- [x] SC-006 makes the text/logic separation observable

## Risk

- [x] Cosmetic-looking change with a real trap identified: behavior currently keyed on the Spanish label (US2)
- [x] Unknown future engine wording degrades to "label unchanged", never to a blank notice
- [x] No data, no process, no queue semantics touched

**Verdict**: ready to plan.
