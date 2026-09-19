# Research: Progress that means something, and a time estimate

## R1. What the machine actually does (measured, not assumed)

**Decision**: Model processing time as `audio_seconds × factor`, where the factor depends on quality preset and PC-usage choice.

**Evidence**: 22 completed meetings, joining each result's `duracion_seg` (from `transcripcion.json`) with the per-file `OK en <n>s` line of the run log and the job's settings:

| Configuration | Samples | Median | Range |
|---------------|---------|--------|-------|
| turbo + speakers, more CPU (Equilibrado default) | 18 | 1.08× | 1.00–1.89× |
| turbo + speakers, keep PC usable | 2 | 1.45× | 1.11–1.80× |
| no speakers (Rápido) | 0 | — | — |
| large-v3 (Máxima calidad) | 0 | — | — |

**Consequence**: `CLAUDE.md` ("2–2.5× the audio duration") and the Equilibrado preset hint ("~2×") are stale by roughly a factor of two and must be corrected (FR-011). The old note that diarization alone takes 1 h 13 min for a 1 h meeting cannot be true when the *whole* job averages 1.08×.

**Alternatives considered**: asking the engine for a duration-based estimate (it has none); timing only the last run (single sample, noisy — the observed range reaches 1.89× when the machine is busy).

## R2. Where the audio duration comes from

**Decision**: Compute it from the work WAV produced by the recorder's own extraction step: it is 16 kHz mono PCM s16le, so `duration = (size − 44 bytes) / 32000`.

**Rationale**: Exact, instant, no extra process. All members of a run are extracted before the engine is launched, so every duration in the run is known when tracking starts. No dependency on the media container or on ffprobe (which this project does not ship).

**Alternatives considered**: `probe_duration` via ffmpeg on the original media (extra process per file, and the media may have several audio tracks); reading duration from a previous transcript (only exists after the fact).

## R3. Weighted progress without inventing phase weights

**Decision**: Derive the percentage from time, not from phases: `progress = active_elapsed / estimated_total`, floored by the transcription-phase percentage while that phase runs, capped at 99% until the transcript exists.

**Rationale**: The engine emits a coarse percentage only for transcription; nothing measurable exists for speaker identification, which is why the bar used to stall. Using elapsed active time makes the bar advance every poll through every phase (SC-002) and monotonic by construction (SC-003), with a single source of truth shared with the finish-time estimate. Flooring with the real transcription percentage keeps the bar honest when the machine runs faster than the estimate.

**Alternatives considered**:

| Option | Why rejected |
|--------|----------------|
| Fixed phase weights (e.g. prep 5% / ASR 40% / speakers 55%) | The split is not observable in the log (no timestamps per line), so the weights would be guesses layered on guesses |
| Measure the split live and persist it per configuration | More state for a cosmetic gain; the time model already produces a smooth bar. Revisit only if users report the bar drifting |
| Keep showing the raw transcription percentage | This is the reported defect |

## R4. Keeping the estimate honest when reality diverges

**Decision**: Recompute every poll. When active elapsed approaches the estimate (≥95% of it) and the file is not finished, extend the estimate (`estimated_total = active_elapsed / 0.95`) so the bar keeps creeping and the finish time slides forward instead of promising a moment that already passed (FR-007).

**Rationale**: The observed range goes up to 1.89×, so underestimates will happen. A sliding estimate is honest; a stuck "0 min left" is the same lie in a new costume.

**Alternatives considered**: clamping to the original estimate (would display past times); widening by the measured p75 up front (would systematically over-promise on the common case).

## R5. Pauses must not consume the estimate

**Decision**: Track *active* elapsed time: accumulate wall time only while the child process is running and not suspended. The notice keeps the paused label and freezes the finish time.

**Rationale**: Recording Always Wins (constitution I) suspends the child; counting that time would make the bar and the finish time drift by the length of the meeting being recorded.

## R6. Learning from history

**Decision**: Persist samples in `%LOCALAPPDATA%\MeetingRecorder\transcripts\speed.json`, keyed by `model | speakers on/off | PC usage`. Keep the last 20 samples per key; use their median once there are ≥3, otherwise the documented default for that key. Written when a file completes, from the audio duration and the measured active time.

**Rationale**: Hybrid as decided in clarification: immediate usefulness from measured defaults, machine-specific accuracy as history accumulates. The median resists the occasional 1.89× outlier caused by background load. Local file, outside OneDrive, consistent with where the queue and logs already live (constitution II/IV).

**Defaults per key** (from R1; the two without samples are derived, marked as estimates and corrected by learning):

| Key | Default | Basis |
|-----|---------|-------|
| turbo, speakers, more CPU | 1.10× | measured median 1.08× (n=18) |
| turbo, speakers, usable | 1.45× | measured median (n=2, weak) |
| turbo, no speakers, more CPU | 0.55× | Rápido skips diarization, documented as about half the work |
| turbo, no speakers, usable | 0.75× | same ratio applied to the usable profile |
| large-v3, speakers, more CPU | 1.60× | heavier ASR: transcription share roughly doubles |
| large-v3, speakers, usable | 2.10× | same ratio applied to the usable profile |

**Alternatives considered**: storing samples inside each job JSON (scattered, hard to aggregate); a single global factor (the usable profile is ~35% slower, which would skew every estimate); learning a per-file factor from the audio itself (no evidence that content matters at this scale).

## R7. Presentation

**Decision**: Notice shows `🎙 <stage> · <file> · archivo N de M — listo ~21:40` plus the weighted bar. Queue summary shows the run total: `Resumen: 1 en curso · 6 en espera · lote listo ~03:20 (mañana)`. Finish times round to 5-minute marks; the day is named when it is not today. While paused, the notice says the estimate is paused.

**Rationale**: Clarification chose finish time over countdown (the question is "will it be done before I need the laptop") and the batch total in the summary line so the notice keeps naming one file (spec 020 FR-005). Five-minute rounding matches an estimate whose realistic error is tens of minutes.

**Alternatives considered**: countdown ("quedan ~1 h 10"), ranges ("1 h – 1 h 20"): both rejected in clarification.

## R8. Short files

**Decision**: Add a fixed startup allowance (model loading) to the estimate: measured runs show a floor of about 40 s even for very short audio, and a batch pays it once.

**Rationale**: Without a floor, a 30 s clip would promise "listo ~now" while model loading alone takes longer than the audio. Kept small and documented, not per-file learned.

## R9. Out of scope

Making transcription faster (GPU, quantization), reordering or prioritizing the queue, and any progress surface beyond the notice and the queue list.
