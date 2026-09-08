# Research: Selected Recordings Folder for Conversion Outputs

## R1. Where does Carpeta de salida actually go?

**Decision**: Persist the picked folder immediately into `AppConfig.output_dir` / `config.json`. Use that resolved absolute path when starting the next recording.

**Rationale**: `_choose_output` only called `QLineEdit.setText`. `_save_config` ran at record start. Restart, scripts (`verify_transcription.py`), and any reader of `AppConfig` kept the **previous** folder. Same-session recording already read `_out_edit`, but preference round-trip (SC-002) failed.

**Alternatives considered**:

| Option | Why rejected |
|--------|----------------|
| Keep saving only on Record | Matches today’s code; fails SC-002 and any conversion that reads config |
| Save on every idle timer | Overkill; picker is explicit |

## R2. Why conversions appear “somewhere else”

**Decision**: Always pass an **absolute** `--output` = `<abs(media.parent)>/Transcripciones`. Do not patch Transcriptor.

**Rationale**: Transcriptor writes `carpeta = RAIZ / o["carpeta_salida"] / archivo.stem`. Pathlib: `RAIZ / abs_path` = `abs_path`, but `RAIZ / "Transcripciones"` (relative) = **inside the Transcriptor project**. Measured:

```text
abs  → D:\Reuniones\Transcripciones
rel  → C:\…\Transcriptor\Transcripciones
```

`output_dir_for(media)` is `Path(media).parent / "Transcripciones"`. If `media_path` is relative (`Grabaciones\foo.mp4`) or only a filename, `--output` is relative and landings are the sibling repo or CWD — not the selected recordings folder.

Work WAVs already go to `%LOCALAPPDATA%\MeetingRecorder\transcripts\work\` (constitution IV). Those are **not** the user-visible “conversiones”.

**Alternatives considered**:

| Option | Why rejected |
|--------|----------------|
| Change Transcriptor to `Path(carpeta_salida)` without RAIZ | Fixes relative too, but touches sibling project; Recorder can guarantee absolute args |
| Copy transcripts into selected folder regardless of media parent | Breaks 009 (imports stay next to source) and would duplicate old meetings |
| Put work WAVs in Carpeta de salida | OneDrive/sync risk; user asked about visible outputs |

## R3. Meetings vs imports after a folder change

**Decision**: New **meetings** (video + `Transcripciones/<stem>/`) follow the selected folder. Imports and already-queued jobs for files that still live elsewhere keep source-adjacent results.

**Rationale**: User report is specifically “cuando se cambia la carpeta de las grabaciones”. Spec 009 already defined import layout. Redirecting in-flight jobs mid-write is unsafe.

**Alternatives considered**: Force all jobs into Carpeta de salida — surprises 009 and copies archives.

## R4. Failure vs silent default

**Decision**: If the selected folder cannot be created/written, fail visibly (`on_error` / dialog). Never substitute `default_output_dir()` after the user picked another path.

**Rationale**: Silent fallback is exactly “conversions somewhere else”. `Recorder.start` already `mkdir`; keep that and do not catch-and-redirect.

## R5. In-progress recording

**Decision**: `Recorder._settings.output_dir` is snapshotted at `start()`. Changing the UI folder during capture does not retarget the current mux. Next `start()` uses the new folder.

**Rationale**: Recording Always Wins; mux path is already bound to `_settings`. Persist the new pick for later (R1) without mutating the active session.
