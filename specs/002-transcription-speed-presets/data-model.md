# Data Model: Transcription Speed Presets

**Feature**: `002-transcription-speed-presets` | **Date**: 2026-07-27

## Entities

### TranscriptionPreset (logical)

| Field | Type | Rules |
|-------|------|-------|
| id | string | One of: `rapido`, `equilibrado`, `maxima_calidad` |
| label_es | string | `Rápido`, `Equilibrado`, `Máxima calidad` |
| model | string | CLI `--model` value |
| beam_size | int | CLI `--beam-size` (≥ 1) |
| no_diarize | bool | If true, pass `--no-diarize` |
| hint_es | string | Short UI explanation |

**Canonical table** (see research.md):

| id | model | beam_size | no_diarize |
|----|-------|-----------|------------|
| rapido | large-v3-turbo | 1 | true |
| equilibrado | large-v3-turbo | 5 | false |
| maxima_calidad | large-v3 | 5 | false |

**Validation**: Unknown id → treat as `equilibrado` (FR-012).

### AppConfig (extension)

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| transcription_preset | string | `equilibrado` | Persisted in `%APPDATA%\MeetingRecorder\config.json` |

Existing fields unchanged (`transcribe_after_recording`, `transcription_language`, etc.).

### TranscriptionJob (extension)

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| preset | string | `equilibrado` | Captured at enqueue |
| model | string | from preset | Denormalized for logs/forward-compat |
| beam_size | int | from preset | Denormalized |
| no_diarize | bool | existing | May be true from preset **or** degraded retry |

**Relationships**:
- User selects preset → stored on `AppConfig`.
- On enqueue, job copies mapping from selected preset (snapshot).
- Worker reads job fields → CLI args (not live AppConfig).

## State transitions

Job lifecycle unchanged (`pending` → `extracting` → `running` → `done`/`error`). Preset fields are immutable after enqueue except `no_diarize` may flip to `true` on degraded retry (existing behavior).

## Serialization

- Config JSON: `"transcription_preset": "rapido"`
- Queue JSON: include `preset`, `model`, `beam_size`, `no_diarize` alongside existing keys; old jobs without these fields → load as equilibrado defaults when re-read (backward compatible).
