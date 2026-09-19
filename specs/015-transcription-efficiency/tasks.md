# Tasks: 015-transcription-efficiency

- [x] T001 `es_wav16k_mono_pcm` + skip convert in Transcriptor `pipeline/audio.py` and `transcribe.py`
- [x] T002 `condition_on_previous_text=False` + in-process Whisper cache in `pipeline/asr.py`
- [x] T003 In-process pyannote cache in `pipeline/diarize.py`
- [x] T004 `transcribe.py` accepts one or more files (`nargs=+`); one `--output` for the group
- [x] T005 Invert `apply_oom_degrade` in Recorder `process_guard.py` (turbo+speakers first)
- [x] T006 `num_speakers` on job/config/UI; `--speakers` when >0
- [x] T007 `batch.py` fingerprint + `build_command` multiple wavs; worker extracts then one CLI; settle by artifacts per file
- [x] T008 Tests: audio prep, OOM order, batch group, speaker snapshot; run existing Recorder tests
