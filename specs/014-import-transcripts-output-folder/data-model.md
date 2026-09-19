# Data Model: Imported Transcripts Follow Carpeta de Salida

## TranscriptionJob (extension)

| Field | Meaning |
|-------|---------|
| `media_path` | Absolute original file (imported or meeting). Never moved. |
| `output_base` | Absolute recordings folder snapshotted at enqueue. Empty string = legacy: derive from `media_path` parent. |
| `result_dir` | Set on success to `{output_dir_for}/<stem>/` |

`output_base` MUST be absolute when non-empty (same canonicalization as media paths). It is the folder the user chose as Carpeta de salida (or the parent of a just-saved meeting MP4), **not** the `Transcripciones` child.

Validation:

- Empty `output_base` is valid (legacy).
- Non-empty must resolve to an absolute directory path; worker writes `{output_base}/Transcripciones/<stem>/`.
- Changing `AppConfig.output_dir` MUST NOT mutate saved jobs.

## Path derivation

```text
output_dir_for(media, output_base) =
    abs(output_base)/Transcripciones     if output_base else abs(media).parent/Transcripciones

result_dir_for(media, output_base) =
    output_dir_for(...) / media.stem
```

CLI `--output` = `output_dir_for(...)` (Transcriptor appends stem).

Must **not** be: factory default after the user picked B, Transcriptor project `output/`, `%LOCALAPPDATA%` work tree, or `{import_parent}/Transcripciones` for a *new* import whose `output_base` is B.

## Import vs meeting

| Origin | `media_path` | `output_base` at enqueue |
|--------|----------------|--------------------------|
| Transcribir archivo / drop | Source file in A | Current Carpeta de salida B |
| Transcribir al terminar | `{B}/{stem}.mp4` | `Path(mp4).parent` (= B unless folder changed mid-capture) |

## State

No new job statuses. `DONE.result_dir` is the source of truth for **Abrir** and already-done re-import.
