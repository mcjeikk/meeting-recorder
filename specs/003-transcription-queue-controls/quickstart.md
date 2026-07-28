# Quickstart: Transcription Queue Controls

## Prerequisites

- Recorder venv + Transcriptor available (same as verify scripts).
- Prefer preset **Rápido** for short waits.

## Steps

1. Launch app; confirm **Idioma** combo shows Español/English/Auto and matches last saved value after restart.
2. Set Idioma = `Auto`, enable Transcribir al terminar, preset Rápido.
3. Record ~5–10 s (or enqueue via existing path); banner shows progress.
4. Click **Cancelar** while pending or running → banner shows cancelada; CPU for that job stops.
5. Confirm queue JSON for that id has `"status": "cancelled"` under `%LOCALAPPDATA%\MeetingRecorder\transcripts\queue\`.
6. With a cancelled/failed job present, click **Limpiar fallidos** → file removed; pending/done untouched.
7. Change Idioma to English, restart app → still English; new enqueue snapshot includes `"language": "en"`.
8. Start recording while cancelling another path if possible → capture unaffected.

## Pass criteria

SC-001–SC-006 from spec satisfied in this manual pass.
