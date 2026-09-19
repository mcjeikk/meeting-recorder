# Requirements Checklist: The queue forgets what it no longer needs

Gate applied to `spec.md` before planning.

## Clarity

- [x] Every requirement states an observable outcome, not an implementation
- [x] The two limits are named with concrete numbers (30 days, ~200 records)
- [x] "Silently" is defined by an acceptance scenario (no message, dialog or delay)
- [x] No placeholders or open questions remain

## Completeness

- [x] What is pruned (finished records + their logs, orphan logs) and what is not (live, failed, cancelled)
- [x] When it runs (app start) and what the user sees (nothing)
- [x] The consequence of pruning on the "already transcribed" answer is specified, not left implicit
- [x] Failure modes covered: unreadable timestamp, locked file, missing folder, unreachable destination

## Consistency

- [x] Does not contradict spec 020 (finished records already hidden from the list)
- [x] Does not contradict the existing manual "clear failed" action
- [x] Does not touch spec 021's learned speed history (explicit in FR-006)
- [x] Retention numbers are justified against measured usage (64 records in three months)

## Testability

- [x] Each success criterion is checkable without the engine (synthetic records + injected clock)
- [x] SC-004 is checkable by pruning a record and importing the file
- [x] Idempotence is an explicit criterion (SC-006)

## Risk

- [x] The dangerous case (re-transcribing hours of audio because a record vanished) is a P1 user story, not a footnote
- [x] Nothing outside the queue folder is in scope (FR-006)
- [x] Limits live in one place so they can be changed deliberately (FR-010)

**Verdict**: ready to plan.
