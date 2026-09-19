# Implementation Plan: Faster Transcription Without Dropping Speakers

**Branch**: `015-transcription-efficiency` | **Date**: 2026-09-09 | **Spec**: [spec.md](./spec.md)

## Summary

Skip a second ffmpeg when the Recorder work WAV is already 16 kHz mono PCM. ASR: `condition_on_previous_text=False`. Cache Whisper + pyannote in one Transcriptor process. Recorder groups compatible pending jobs and passes all WAVs in one argv (log file, not pipe). OOM: turbo+usable with speakers first. Optional `--speakers` from UI snapshot. No fused venv; Recording Always Wins.

## Technical Context

**Language/Version**: Python 3.11.9 (both venvs)

**Primary Dependencies**: faster-whisper, pyannote.audio, ffmpeg

**Storage**: Job JSON + work WAVs in `%LOCALAPPDATA%\MeetingRecorder\transcripts\`

**Testing**: unittest in Recorder; Transcriptor tests without loading torch models

**Target Platform**: Windows desktop

**Constraints**: argv lists; stdout to log; constitution I–V

## Constitution Check

- I PASS suspend/no-start while recording
- II PASS local
- III PASS sibling CLI; cache only inside Transcriptor process
- IV PASS log file, not stdin daemon
- V PASS batch = extra wavs on existing CLI

## Structure

Transcriptor: `pipeline/audio.py`, `asr.py`, `diarize.py`, `transcribe.py`  
Recorder: `process_guard.py`, `jobs.py`, `worker.py`, `integration.py`, `batch.py`, `config.py`, `main_window.py`
