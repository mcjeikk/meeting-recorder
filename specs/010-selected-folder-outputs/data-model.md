# Data Model: Selected Recordings Folder for Conversion Outputs

## AppConfig.output_dir

Remembered **Carpeta de salida**. Stored in `%APPDATA%\MeetingRecorder\config.json`.

| Field | Rule |
|-------|------|
| `output_dir` | Absolute filesystem path. Written as soon as the user confirms **Cambiar…**, not only when recording starts. Never a relative path (relative strings are resolved before save). Empty/corrupt config still initializes to the factory default (`~/Videos/Grabaciones` or `~/Grabaciones`). |

No new JSON keys.

## RecordingSettings.output_dir

Per-session snapshot for **one** recording.

| Field | Rule |
|-------|------|
| `output_dir` | Absolute Path. Taken from the UI field (resolved) at **start**. Unchanged for the life of that capture, even if the user picks another folder mid-recording. |
| MP4 path | `{output_dir}/{recording_stem}.mp4` |

## User-visible transcript location (meetings)

Derived from the **media file**, which for new meetings lives under the selected folder:

| Entity | Path |
|--------|------|
| Transcript tree | `{abs(media.parent)}/Transcripciones/` (`output_dir_for`) |
| Per-meeting folder | `{that}/{stem}/` (`result_dir_for`) |
| CLI `--output` | Absolute `output_dir_for(media)` (Transcriptor then appends `stem`) |

Must **not** be: factory default recordings dir, previous folder A after the user chose B, Transcriptor project `output/` or `Transcripciones/`, or `%LOCALAPPDATA%` work tree.

## Internal work files (unchanged)

| Entity | Path |
|--------|------|
| Queue JSON | `%LOCALAPPDATA%\MeetingRecorder\transcripts\queue\{id}.json` |
| Logs | `...\logs\{stem}_{id}.log` |
| Work WAV | `...\work\{id}\{stem}.wav` |

These MUST stay off cloud sync. They are not the user-visible destination.

## TranscriptionJob.media_path

| Field | Rule |
|-------|------|
| `media_path` | Absolute, resolved path of the source file (meeting MP4 or import). Enqueue must canonicalize so `--output` cannot be relative to CWD or Transcriptor RAIZ. |

Identity/dedupe remains `os.path.normcase` as today.

## Imports (009, unchanged)

`result_dir` = `{parent of original}/Transcripciones/{stem}/`. Original is not copied into `AppConfig.output_dir`.
