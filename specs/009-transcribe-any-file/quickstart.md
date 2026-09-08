# Quickstart: Transcribe Any Audio File

## Prerequisites

- Recorder `.venv` (Python 3.11)
- Sibling Transcriptor available (`transcribe.py` + its `.venv`)
- A short sample **not** produced in this session (e.g. an mp3/m4a/wav, or an old meeting mp4)

## Automated

From Recorder repo root:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_transcribe_any_file tests.test_transcription_queue_controls tests.test_recording_names -v
```

Optional headless UI (no `show()`, offscreen):

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
$env:PYTHONIOENCODING = "utf-8"
.\.venv\Scripts\python.exe -m unittest tests.test_transcribe_any_file -v
```

## Manual (UI)

1. Launch Recorder. In group 4, confirm **Transcribir archivo…** is visible next to **Transcribir al terminar**, and that preset/language sit below both.
2. Set preset **Rápido** and language **Español**.
3. Click **Transcribir archivo…**, pick a short supported file. Original stays in place. Banner shows “En cola”.
4. When done, **Abrir** opens `<parent>/Transcripciones/<stem>/`. Repeat import of the same path → message that a transcript already exists; Abrir still works; no second long job.
5. Drag another supported file onto the window (overlay appears) → enqueued like the picker.
6. Drag a `.txt` or a folder → clear in-window message; no job.
7. Start **Grabar**, then transcribe/drop a file → recording continues; transcription waits or stays suspended until you stop.
8. Cancel / retry / clear failed behave as with meeting jobs.

## Expected pipeline (no Transcriptor change)

Recorder extracts WAV 16 kHz mono into `%LOCALAPPDATA%\MeetingRecorder\transcripts\work\{job_id}\` (Mezcla / unique / amix), then `transcribe.py` on that WAV. Never pass a multi-track Recorder MP4 straight to Transcriptor `convertir_a_wav16k`.
