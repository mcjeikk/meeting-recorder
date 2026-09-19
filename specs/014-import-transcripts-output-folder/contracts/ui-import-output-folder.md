# UI contract: import transcripts vs Carpeta de salida

## Destination

| Action | User-visible transcripts |
|--------|--------------------------|
| Transcribir archivo… / drop (new job) | `{Carpeta de salida at enqueue}/Transcripciones/{stem}/` |
| Transcribir al terminar (new meeting) | `{folder the MP4 was saved to}/Transcripciones/{stem}/` |
| Legacy job with empty `output_base` | `{media.parent}/Transcripciones/{stem}/` |

Original media is not copied. **Abrir** uses `job.result_dir` after success.

## Copy

- Import hint MUST mention Carpeta de salida (or “la carpeta de grabaciones”) as the transcript destination.
- MUST NOT say imported results stay next to the source file.

## Worker / CLI

```
JobStore.enqueue(..., output_base=<abs folder or "">)
build_command(..., output_dir_for(media, output_base=job.output_base))
```

`--output` is always absolute. Transcriptor source is not modified.

## Non-goals

- Second folder picker for transcripts only
- Relocating old source-adjacent `Transcripciones` trees
- Copying imported MP4/WAV into Grabaciones
