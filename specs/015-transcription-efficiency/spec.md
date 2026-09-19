# Feature Specification: Faster Transcription Without Dropping Speakers

**Feature Branch**: `015-transcription-efficiency`

**Created**: 2026-09-09

**Status**: Implemented

**Input**: User: implement the efficiency analysis. Always identify speakers (meetings and interviews). Not only app-generated media. Skip redundant WAV convert; `condition_on_previous_text=False`; OOM lightens the model before dropping speakers; reuse models across queued files; optional speaker count.

## Clarifications

### Session 2026-09-09

- Q: Must speaker labels always run? → A: Yes for the normal path (Equilibrado/Máxima, meetings and interviews, imported or recorded). Rápido may still omit speakers as an explicit user choice. Memory failure drops speakers only after a lighter-model retry, and must say so.
- Q: Are imported files in scope for prep optimizations? → A: Yes. Do not assume Mezcla-track MP4. Still extract/normalize; skip only a *second* convert when the work WAV is already 16 kHz mono PCM.
- Q: How to reuse models without a fused venv or a stdin daemon (child must survive app close)? → A: Cache models inside one Transcriptor process, and let Recorder pass several compatible queued WAVs in one CLI argv (stdout still a log file).
- Q: Speaker count? → A: Optional Auto (default) or an exact N snapshotted at enqueue (`--speakers`).

## User Scenarios & Testing

### User Story 1 - Prep once (Priority: P1)

Imported or recorded media is converted to 16 kHz mono PCM at most once before ASR/diarization.

**Independent Test**: A 16 kHz mono PCM WAV is not fed through ffmpeg a second time; an mp3/mp4 still gets one conversion.

### User Story 2 - Speakers survive memory pressure (Priority: P1)

Long file OOM retries with turbo + usable PC **with speakers still on**. Only a later failure may omit speakers, visibly.

### User Story 3 - Several files, one model load (Priority: P1)

Three compatible queued files (same language/model/speakers/destination) run in one sibling CLI so Whisper and pyannote load once. App close does not kill that CLI (log file, not stdin). Recording still suspends it.

### User Story 4 - Optional speaker count (Priority: P2)

User can set Auto or 2/3/… before import; that N is stored on the job.

### User Story 5 - Long-form ASR without repeat loops (Priority: P2)

ASR does not condition on previous text (same or better meeting text, less looping).

## Requirements

- **FR-001**: If work audio is already WAV 16 kHz mono PCM, Transcriptor MUST NOT run a second ffmpeg conversion.
- **FR-002**: Otherwise convert/extract once (Recorder Mezcla / single / amix, then Transcriptor only if still not 16 kHz mono PCM). Original media is never moved.
- **FR-003**: ASR MUST use `condition_on_previous_text=False`.
- **FR-004**: OOM degrade MUST first switch to turbo + usable PC keeping diarization; only then may it set no-diarize with a visible note.
- **FR-005**: Whisper and pyannote MUST be cached for the life of one Transcriptor process.
- **FR-006**: Recorder MUST pass every compatible pending job’s work WAV in a single `transcribe.py` argv when more than one is ready; success per file is output artifacts (not only the process exit code).
- **FR-007**: Optional speaker count Auto or N, snapshot on job, `--speakers N` when N is set.
- **FR-008**: Recording Always Wins (no start while recording; suspend/resume). No fused venv. Argv lists. Work files in local app data.
- **FR-009**: Rápido remains an explicit no-speakers choice; it is not the OOM first step.

## Success Criteria

- **SC-001**: Unit test: 16 kHz mono PCM WAV is detected as reusable (no second convert).
- **SC-002**: Unit test: OOM on Máxima keeps speakers on the first degrade and uses turbo.
- **SC-003**: Unit test: three pending jobs with the same fingerprint group into one batch; a different language does not.
- **SC-004**: Unit test: enqueue with N=2 stores 2; Auto stores 0/empty.
- **SC-005**: Existing import / selected-folder / queue / headless tests still pass.

## Assumptions

- Not replacing pyannote community-1 in this feature (same speaker engine, cheaper load/prep).
- Compatible batch = same language, model, beam, no_diarize, speaker N, output_base.
- One `--output` folder per CLI (same Carpeta de salida snapshot).
