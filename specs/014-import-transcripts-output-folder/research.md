# Research: Imported Transcripts Follow Carpeta de Salida

## R1. Why imports ignore Carpeta de salida today

**Decision**: `output_dir_for` / `result_dir_for` take an optional `output_base`. When set, user-visible output is `{abs(output_base)}/Transcripciones/{stem}/`. When omitted/empty, keep `{abs(media.parent)}/Transcripciones/{stem}/` (meetings whose MP4 already lives in Carpeta de salida, and legacy jobs).

**Rationale**: Today `output_dir_for(media) = media.parent / "Transcripciones"`. Meetings work because the MP4 is already in Carpeta de salida. Imports keep `media_path` at the source (009 FR-005, still required), so parent is Downloads/USB/etc. Spec 010 FR-006 explicitly forbade redirecting imports; the user has now reversed that.

**Alternatives considered**:

| Option | Why rejected |
|--------|----------------|
| Always use `AppConfig.output_dir` at run time | Redirects in-flight jobs if the user changes the folder; unsafe mid-write |
| Copy imported media into Carpeta de salida then use parent | Duplicates large videos; 009 FR-005 / constitution V |
| Change Transcriptor default output | Still need an absolute `--output`; sibling project stays untouched |

## R2. Snapshot on the job

**Decision**: Add `output_base: str` on `TranscriptionJob`, captured in `JobStore.enqueue(..., output_base=)`. Imports pass the resolved Carpeta de salida from the UI. Post-recording enqueue passes `Path(mp4).parent` (the folder the video actually landed in). Worker never re-reads the live config for `--output`.

**Rationale**: Same snapshot pattern as preset/language. Recording-in-progress can have a different mux folder than the current text field (010 R5).

**Alternatives considered**: Live config at `_process` time — fails SC-004.

## R3. Legacy jobs

**Decision**: Missing/empty `output_base` → media parent (old behavior). Do not rewrite existing queue JSON.

**Rationale**: In-flight Parte N jobs must not jump destination mid-write (spec FR-005).

## R4. `--output` stays absolute

**Decision**: Keep passing absolute `Transcripciones` into `build_command`. Do not patch Transcriptor.

**Rationale**: Unchanged from 010 R2; relative paths land inside the sibling repo.

## R5. Docs and 009/010

**Decision**: This spec supersedes 009 FR-006 and 010 FR-006/US3 for *new* imports. Leave historical spec text with a supersession note; README and UI hint must stop saying results sit beside the imported file.

**Rationale**: Specs are the contract; silent code divergence is what 010 was written to prevent.
