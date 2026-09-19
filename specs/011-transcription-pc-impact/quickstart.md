# Quickstart: 011-transcription-pc-impact

1. Open Recorder → section **4**.
2. Set **Velocidad / calidad** to **Máxima calidad** (or Equilibrado).
3. **Uso del PC** defaults to **Usar más CPU**. Switch to **Dejar el PC usable** only if the desktop must stay responsive.
4. Transcribe a short file or finish a short recording with transcribe-on-finish.
5. Confirm other apps still accept input (browser, Explorer) while the banner shows progress.
6. Optional: switch to **Usar más CPU** only when you can leave the machine; new jobs after that change use the heavy path.
7. Restart the app: **Uso del PC** should still show the last choice.

Automated: `python -m unittest tests.test_pc_impact tests.test_transcription_queue_controls -v`
