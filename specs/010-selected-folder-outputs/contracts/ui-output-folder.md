# UI contract: Carpeta de salida

## Control

- Group **4. Carpeta de salida**
- Read-only path field + **Cambiar…** (`QFileDialog.getExistingDirectory`)
- Dialog start directory: current field text, else home

## On confirm (user picks a folder)

1. Resolve to an absolute path.
2. Show that path in the field.
3. Persist immediately to `AppConfig.output_dir` / `config.json`.
4. Do **not** require starting a recording for the preference to stick.

## On cancel

Leave field and config unchanged.

## Next recording

`RecordingSettings.output_dir` = resolved field text. Mux writes `{that}/{stem}.mp4`.

If mkdir/write fails: existing error path (status + dialog). Do not write the MP4 or transcripts into the factory default or the previous folder.

## Mid-recording change

The capture already in progress keeps its start-time folder. The persisted preference applies to the **next** recording.

## Open folder / open transcript

- Open recordings folder for a just-finished meeting: directory of that MP4 (under the selected folder for new meetings).
- Open transcript: `result_dir` under `{selected}/Transcripciones/{stem}/` for those meetings.

## Imports

Picker default directory may start at Carpeta de salida (convenience). Result layout stays source-adjacent (009). This contract does not relocate imports into Carpeta de salida.
