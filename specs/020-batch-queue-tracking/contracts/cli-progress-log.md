# Contract: plain log of the Transcriptor as a progress source

The Recorder runs the sibling CLI with `TRANSCRIPTOR_PLAIN=1` and redirects stdout+stderr to one log file per run (never a pipe, so the child survives app close). This is the contract the Recorder relies on. The Transcriptor is **not** modified by this feature; if these lines change, `app/transcription/cli_progress.py` is the only place to update.

## Lines consumed

| Line (as printed) | Meaning for the Recorder |
|-------------------|--------------------------|
| `> Procesando: <name>.wav` | The engine switched to this file. Becomes the live job; percentage resets to 0. Also delimits this file's log section. |
| `  - Convirtiendo audio a WAV 16 kHz...` | Stage "Preparando audio…" |
| `  - Audio ya en WAV 16 kHz; se omite reconversión.` | Stage "Audio listo…" |
| `    transcribiendo... NN%` | Percentage of the live file (emitted about every 10%) |
| `    -> dispositivo: cuda` | Stage notes GPU |
| `  - Identificando hablantes (diarizacion)...` | Long phase: percentage becomes indeterminate |
| `  [!] La diarizacion no se completo (...)` / `[!] Diarizacion solicitada pero no hay HUGGINGFACE_TOKEN` | Note "sin hablantes" on the live job |
| `  [X] Error con <name>: <reason>` | Failure reason, attributed to the file whose section contains it |
| `  OK en <n>s  ->  <folder>` | Informational only; completion is decided by `transcripcion.txt` |

## Rules

- **C-1**: Success is never concluded from the log. A file is `done` only when `<output>/Transcripciones/<stem>/transcripcion.txt` exists (the batch exit code is global).
- **C-2**: The file name printed by the engine is the **work WAV** name, i.e. `<media stem>.wav`. Matching must compare file names (and stems), tolerating accents, spaces and brackets; never compare full paths.
- **C-3**: Everything between one `> Procesando:` and the next belongs to that file only. Text outside any section (the Recorder's own `--- intento … ---` header, the final `Finalizado. N/M`) belongs to no file.
- **C-4**: An absent section for a file means the engine never reached it: no error is attributed to it and it returns to the queue.
- **C-5**: The log is read incrementally by byte offset; each read must tolerate a partially written line and must never block or truncate the file.
- **C-6**: Percentages are advisory. `None` = nothing new, `0..100` = current file, `-1` = indeterminate (no number should be shown).

## Recorder-side header

The Recorder appends one header per attempt before launching:

```text
--- intento <n> · <k> archivo(s) · <track description> ---
```

It must not be parsed as engine output; it exists to make the log readable when diagnosing a batch.
