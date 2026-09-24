# Implementation Plan: Recorder and Transcriptor live in one repository

**Branch**: `029-single-repository` | **Date**: 2026-09-24 | **Spec**: [spec.md](./spec.md)

## Summary

Rewrite a copy of the Transcriptor's history so every commit lives under `transcriptor/`, then merge it into the Recorder with `--allow-unrelated-histories`: one repository, per-file history intact. Autodetection learns a notion of a *complete* Transcriptor (command line **and** environment) and tries the bundled folder first, then the sibling layouts. Documentation becomes one clone, two environments. A `run_all_tests.ps1` runs each suite in its own environment. The old repository gets a pointer README and is archived. Then the user's installation migrates, and a fresh clone proves it.

## Technical Context

**Language/Version**: Python 3.11.9 for both parts, each in its own `.venv`.

**Primary Dependencies**: none new. Git (built-in `filter-branch`; `git filter-repo` is not installed and the Transcriptor has four commits), `gh` for archiving.

**Storage**: none new. The Transcriptor's `.env` stays next to it (`transcriptor/.env`), ignored by both `.gitignore` files.

**Testing**: discovery tests extended for completeness and precedence; both suites on a fresh clone; end-to-end verification on the migrated installation and on the fresh clone.

**Target Platform**: Windows.

**Constraints**: the current installation must keep transcribing at every step; the user's unversioned files in `Apps\Transcriptor` are not touched.

## Constitution Check

- I. Recording Always Wins — PASS (untouched)
- II. Privacy Is Local — PASS (the token stays out of version control; checked, not assumed)
- III. Transcription stays a sibling subprocess — PASS in substance: it stays a subprocess with its own environment; "sibling" now means a sibling folder inside the same repository. This is the point of the design, not a violation of it.
- IV. Robust paths and processes — PASS (the incomplete bundled folder can never be chosen)
- V. Simplicity — PASS (one repository, less layout to explain)

## Design decisions

1. **History under the new path, not `git subtree`.** `subtree add` keeps the old commits at their old root paths, so `git log transcriptor/transcribe.py` would start at the merge. Rewriting a throwaway clone with `filter-branch --index-filter` moves every commit under `transcriptor/`, and the merge then gives real per-file history.
2. **Complete means runnable.** The bundled folder exists in every clone, environment or not. Detection that only looked for `transcribe.py` would pick it and break a working setup the moment the repository updates. A candidate is usable only with `.venv\Scripts\python.exe` and `transcribe.py`; an incomplete one is only a last resort so the error can name it.
3. **Order**: bundled `transcriptor/`, then `..\meeting-transcriber`, `..\Transcriptor`, `..\..\Transcriptor`. Bundled first because in the new layout it is the one that matches the Recorder's version.
4. **A saved path wins only when it is complete.** Today's saved paths were written by the default factory, not chosen by hand, so an incomplete one is not a preference worth honouring over a working Transcriptor.
5. **Fresh environment for the migration.** Moving a venv leaves launchers pointing to the old path (it happened once already). The bundled environment is created from `requirements.lock.txt` to reproduce the validated one exactly, and pinned against OneDrive's Files On-Demand like the others.
6. **Archive, don't delete.** The old repository keeps its history and links; archiving makes it read-only and reversible.

## Project Structure

```text
transcriptor/                     # the whole Transcriptor, history preserved
app/core/config.py                # completeness + precedence in detection
tests/test_transcriptor_discovery.py
run_all_tests.ps1                 # both suites, each in its own environment
README.md                         # one clone, two environments
transcriptor/README.md            # usage inside the repository, standalone still documented
CLAUDE.md                         # the layout and why the environments stay separate
specs/029-single-repository/
```

## Complexity Tracking

> No constitution violations; section intentionally empty.
