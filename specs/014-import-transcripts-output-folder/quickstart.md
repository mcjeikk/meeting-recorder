# Quickstart: 014 import transcripts → Carpeta de salida

## Automated

From the Recorder repo (venv):

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_selected_folder_outputs tests.test_transcribe_any_file -v
```

Expect:

- Import media in folder A with `output_base=B` → `result_dir_for` under B, not A
- Meeting MP4 already in B → transcripts still under B
- `enqueue(..., output_base=B)` stores an absolute `output_base`
- Empty `output_base` still uses media parent (legacy)
- Original file is not copied (existing import tests)

## Manual (SC-001–003)

1. In the app, **Cambiar…** Carpeta de salida to an empty folder B.
2. **Transcribir archivo…** and pick a short file that lives in a different folder A (or drop it).
3. Confirm the queue lists the file; original still only in A.
4. When done, **Abrir** → Explorer under `B\Transcripciones\<stem>\` with txt/srt/json.
5. Confirm A has no new `Transcripciones` tree for that file.

## Snapshot (SC-004)

Queue an import with B selected, then change Carpeta de salida to C before the job runs. That job’s results still appear under B.
