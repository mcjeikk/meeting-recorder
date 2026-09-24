# Tasks: Recorder and Transcriptor live in one repository

**Input**: [spec.md](./spec.md), [plan.md](./plan.md)

## Phase 1 — Detection first (so the move cannot break a working setup)

- [x] **T001** `tests/test_transcriptor_discovery.py`: a folder with `transcribe.py` but no environment is not usable and is never chosen over a complete one; the bundled folder wins when complete; sibling layouts still found; an incomplete saved path yields to a complete candidate; a complete saved path wins. (FR-003, FR-004, FR-005)
- [x] **T002** `app/core/config.py`: completeness check and the new order. (FR-003, FR-004, FR-005) — commit `2c16581`.
- [x] **T003** Suite green; the current installation still resolves to `Apps\Transcriptor`.
  *Evidence*: 250 tests OK; `AppConfig.load().transcriptor_dir` = `...\Apps\Transcriptor`.

## Phase 2 — The move

- [x] **T004** Rewrite a throwaway clone of the Transcriptor so every commit lives under `transcriptor/`; merge it into the Recorder with `--allow-unrelated-histories`. (FR-001) — merge `4393886`.
- [x] **T005** Check: `git log -- transcriptor/transcribe.py` shows the pre-move commits; `git check-ignore` confirms `transcriptor/.env`, `transcriptor/.venv/` and media are ignored. (SC-002, FR-010)
  *Evidence*: 3 commits back to `36d2b0c Commit inicial`; the old repo's head `80c9560` is `6c5d521` here. `.env`, `.venv/`, `output/`, `.mp4`, `.wav` all ignored. Every `.env.example` in history holds only the `hf_xxxx` placeholder.
- [x] **T006** With the bundled folder present and no environment in it, the current installation still transcribes through `Apps\Transcriptor`. (SC-003)

## Phase 3 — Documentation and tooling

- [x] **T007** `README.md`: one clone, then the two environments, token, check. (FR-006)
- [x] **T008** `transcriptor/README.md`: installed from inside the repository; standalone use kept. (FR-009)
- [x] **T009** `run_all_tests.ps1`: both suites, each with its own interpreter, one exit code. (FR-007, SC-005)
  *Evidence*: "Ran 250 … OK" + "Ran 10 … OK", exit 0. ASCII only: PowerShell 5.1 reads BOM-less `.ps1` as ANSI.
- [x] **T010** `CLAUDE.md`: new layout; environments stay separate and why.
- [x] **T011** Commit and push. — `7440154` on `origin/main`.

## Phase 4 — Old repository

- [x] **T012** `meeting-transcriber`: README pointing to `meeting-recorder/transcriptor`, pushed; repository archived. (FR-008, SC-006)
  *Evidence*: head `5ad4f42 Moved: …`, description "ARCHIVADO: …", `archived: true`.

## Phase 5 — Migrate the current installation

- [x] **T013** Create `transcriptor\.venv` from `requirements.lock.txt` (torch +cpu first), copy the `.env`, pin the environment against Files On-Demand.
  *Evidence*: torch exit 0, lock exit 0 (9 min); `.env` with a real token, ignored; `attrib` shows `P`.
- [x] **T014** Point `transcriptor_dir` to the bundled folder; `smoke_test.py` and `verify_transcription.py --quick` with speakers. (SC-004)
  *Evidence*: with the Recorder closed (it saves `config.json` on almost every UI change), `transcriptor_dir` was switched to `Recorder\transcriptor` (backup `config.json.bak-029`). `smoke_test.py` reports that folder and the token; `verify_transcription.py --quick` on the 2026-09-23 recording, using the real configuration: `OK en 102s`, 2 speakers.

## Phase 6 — Acceptance

- [x] **T015** Fresh clone of the one repository into a clean folder with a space in its path; install both parts as the README says; `run_all_tests.ps1` green; with an empty app configuration, `verify_transcription.py --quick` on an audio file returns a transcript with speakers. (SC-001, SC-005)
  *Evidence* (`%TEMP%\clon 029`, clone of `7440154`, `APPDATA` pointed at an empty folder): app install 1 min, engine install 8 min (torch + `requirements.txt`, both exit 0); 250 + 10 tests OK; `smoke_test.py` found the clone's own `transcriptor` and the token; a 2-minute mp3 made from a real recording gave `OK en 132s`, three artifacts, **2 speakers**. 12 min 27 s end to end. The folder, with its token copy, was deleted afterwards.
