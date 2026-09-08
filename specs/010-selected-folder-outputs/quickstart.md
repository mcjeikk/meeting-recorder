# Quickstart: Selected folder outputs

## Automated

From the Recorder repo (project `.venv`):

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_selected_folder_outputs -v
```

Expected: all tests pass. They prove that after switching the destination to a temp folder B (not the factory default):

- resolved `output_dir` is B (absolute)
- a meeting MP4 path is under B
- `output_dir_for` / `result_dir_for` are under `B/Transcripciones/…`
- `build_command` `--output` is that absolute Transcripciones path (not relative, not default, not LOCALAPPDATA)

Optional (existing, do not require GPU/ASR):

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_transcribe_any_file tests.test_recording_names -v
```

## Manual

1. Note current Carpeta de salida (A), often `Videos\Grabaciones`.
2. **Cambiar…** → empty folder B (another drive or Desktop subfolder is fine).
3. Quit and reopen the app: field still shows B.
4. Enable **Transcribir al terminar** if the sibling tool is available.
5. Record ~5 s, stop.
6. Confirm `B\<nombre>_<timestamp>.mp4` exists.
7. When conversion finishes, confirm `B\Transcripciones\<mismo stem>\transcripcion.txt` (and srt/json). Nothing new for that meeting in A, in `~\Videos\Grabaciones` if B is elsewhere, or under the Transcriptor project `output\` folder.
8. **Abrir carpeta** / open transcript land under B.

Imports (regression): **Transcribir archivo…** on a file that lives outside B; results still appear next to that file, not copied into B.
