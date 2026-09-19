# Tasks: A momentary file lock must not fail a transcription

**Input**: [spec.md](./spec.md) · Found by the trail of spec 026 on its first real batch.

**Note on process**: no separate `plan.md` or `research.md` for this one. The change is two methods of `JobStore` and the evidence is a single recorded line; a plan document would restate the spec. The design decisions are in the code comments and in the spec's Assumptions.

## Phase 1 — Tests first

- [x] **T001** `tests/test_job_store_save.py`: six threads saving the same job in a loop finish with no errors, a readable record and no leftover temporary file. (FR-002, FR-004, SC-002)
- [x] **T002** Same file: a replace that fails twice is retried and the saved state is intact. (FR-001, SC-001)
- [x] **T003** Same file: a permanent failure raises and leaves no temporary file. (FR-003, FR-004, SC-005)
- [x] **T004** Same file: two threads never share a temporary name, and the name carries the process id. (FR-002)
- [x] **T005** Same file: a stray temporary file is not counted as a job. (FR-009, SC-006)

## Phase 2 — Implementation

- [x] **T006** `app/transcription/jobs.py`: the temporary file is named per process and thread. (FR-002)
- [x] **T007** `app/transcription/jobs.py`: saving retries on a momentary failure within a short budget, then raises; the temporary file is always removed. (FR-001, FR-003, FR-004, FR-008)
- [x] **T008** `app/transcription/jobs.py`: reading retries on a momentary failure but answers absence immediately, and still ignores corrupt records. (FR-005, FR-006, FR-007)

## Phase 2b — What the stress test caught (the first fix was not enough)

The unique temporary name plus a retry left T001 failing about one run in three:
`PermissionError(13)` after all retries. Cause: on Windows an **open reader**
prevents replacing the file, so the app's own reads were blocking its own
writes — retrying only lowered the odds.

- [x] **T012** `app/transcription/jobs.py`: serialise the app's own record reads and writes with a per-store lock, leaving the retry for interference from outside the app. (FR-002a)
- [x] **T013** `tests/test_job_store_save.py`: harden T001 — eight threads, forty rounds each, reading the whole queue while others write, and assert that a busy record never reads as absent. (SC-002)
- [x] **T014** Run that test twelve times in a row: twelve passes. A concurrency test that passes once proves nothing.

## Phase 3 — Verification

- [x] **T009** Full suite green: 233 tests, five runs in a clean worktree (the flake that T012 fixed only showed in repeats).
- [x] **T010** `verify_transcription.py --quick` passes end to end against the real engine.
- [x] **T011** A real two-file batch leaves a trail with no `failed` entry caused by a record lock (the symptom that started this).

## Out of scope, recorded on purpose

- The learned speed history (`speed.json`) uses the same fixed-temporary pattern. A failure there is already swallowed by design, so it cannot fail a job; left alone rather than changed without evidence.
- Indexing the queue to avoid re-reading every record per query stays deferred (it was considered in spec 023 and bounded by pruning instead).
