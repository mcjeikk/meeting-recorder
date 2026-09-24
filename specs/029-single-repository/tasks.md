# Tasks: Recorder and Transcriptor live in one repository

**Input**: [spec.md](./spec.md), [plan.md](./plan.md)

## Phase 1 — Detection first (so the move cannot break a working setup)

- [ ] **T001** `tests/test_transcriptor_discovery.py`: a folder with `transcribe.py` but no environment is not usable and is never chosen over a complete one; the bundled folder wins when complete; sibling layouts still found; an incomplete saved path yields to a complete candidate; a complete saved path wins. (FR-003, FR-004, FR-005)
- [ ] **T002** `app/core/config.py`: completeness check and the new order. (FR-003, FR-004, FR-005)
- [ ] **T003** Suite green; the current installation still resolves to `Apps\Transcriptor`.

## Phase 2 — The move

- [ ] **T004** Rewrite a throwaway clone of the Transcriptor so every commit lives under `transcriptor/`; merge it into the Recorder with `--allow-unrelated-histories`. (FR-001)
- [ ] **T005** Check: `git log -- transcriptor/transcribe.py` shows the pre-move commits; `git check-ignore` confirms `transcriptor/.env`, `transcriptor/.venv/` and media are ignored. (SC-002, FR-010)
- [ ] **T006** With the bundled folder present and no environment in it, the current installation still transcribes through `Apps\Transcriptor`. (SC-003)

## Phase 3 — Documentation and tooling

- [ ] **T007** `README.md`: one clone, then the two environments, token, check. (FR-006)
- [ ] **T008** `transcriptor/README.md`: installed from inside the repository; standalone use kept. (FR-009)
- [ ] **T009** `run_all_tests.ps1`: both suites, each with its own interpreter, one exit code. (FR-007, SC-005)
- [ ] **T010** `CLAUDE.md`: new layout; environments stay separate and why.
- [ ] **T011** Commit and push.

## Phase 4 — Old repository

- [ ] **T012** `meeting-transcriber`: README pointing to `meeting-recorder/transcriptor`, pushed; repository archived. (FR-008, SC-006)

## Phase 5 — Migrate the current installation

- [ ] **T013** Create `transcriptor\.venv` from `requirements.lock.txt` (torch +cpu first), copy the `.env`, pin the environment against Files On-Demand.
- [ ] **T014** Point `transcriptor_dir` to the bundled folder; `smoke_test.py` and `verify_transcription.py --quick` with speakers. (SC-004)

## Phase 6 — Acceptance

- [ ] **T015** Fresh clone of the one repository into a clean folder with a space in its path; install both parts as the README says; `run_all_tests.ps1` green; with an empty app configuration, `verify_transcription.py --quick` on an audio file returns a transcript with speakers. (SC-001, SC-005)
