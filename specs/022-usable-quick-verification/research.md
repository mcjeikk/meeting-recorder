# Research: A quick check that can actually be run

## R1. Why the check is unusable today

**Evidence**: running `.\.venv\Scripts\python.exe verify_transcription.py --quick` on 2026-09-18 printed:

```text
Ya existe una transcripción en C:\Users\...\Downloads\Transcripciones\1er reunion arq empresarial christian braatz
Usa --force para sobreescribirla (ojo: --quick la dejaría sin hablantes).
```

The script picks the newest `.mp4` in the user's output folder and computes its destination with `result_dir_for(media, output_base=cfg.output_dir)` — the **real** destination. Since every recording on this machine is already transcribed, the only way forward is `--force`, which overwrites a real transcript, and with `--quick` would replace a speaker-labelled transcript with one without speakers.

**Decision**: a verification run never computes a real destination. It passes its own temporary `output_base`, so the "already exists" guard is about its own throwaway folder and effectively never triggers.

## R2. How to make it quick without faking the path

**Decision**: cut a slice of a real recording with `ffmpeg -ss 0 -t <N> -map 0 -c copy`, then queue that slice.

**Rationale**: stream copy is ~1 s and preserves every audio track **and** their names, so the part most likely to break silently (choosing the "Mezcla" track instead of only "Sistema", per CLAUDE.md) is exercised for real. Re-encoding would be slower and could normalise away the multi-track layout that the extraction logic depends on.

**Alternatives considered**:

| Option | Why rejected |
|--------|----------------|
| Synthetic audio (ffmpeg sine / testsrc) | Would not exercise track selection, which is the trap that actually bit; also produces nonsense transcripts |
| Transcribe the whole recording | Hours (measured ~1.08× the audio) — the opposite of a smoke test |
| Re-encode the slice | Slower, and changes the track layout the check should be validating |
| Keep a committed sample media file in the repo | Meeting audio is confidential (constitution II) and would bloat the repo |

**Sample length**: 60 s by default. Long enough that the engine emits real progress and produces non-trivial artifacts; short enough that even with speakers the run stays in minutes.

## R3. Isolation as a requirement, not a nicety

**Decision**: one temp folder per run holds queue, logs, work audio, the destination and the speed history. Deleted on success, kept (and printed) on failure.

**Rationale**: the audit found a concrete incident — the speed history introduced in spec 021 was being written to the machine's real file by test and verification code, with millisecond "runs", which poisoned the learned factor to 0.00× and would have shown "listo en 1 min" for every real job. Spec 021's remediation moved the history next to its queue; this feature depends on that and asserts it.

## R4. What a pass must mean

**Decision**: a run passes only if all of these hold — the artifacts exist (`transcripcion.txt`, `.srt`, `.json`), progress updates were received naming the sampled file, a finish-time estimate was received, and (when requested) the structured result reports at least one speaker.

**Rationale**: the defects this project actually suffered were not "no output": they were *silent* degradations — speakers dropped with exit code 0, and status that stopped following reality. A verification that only checks for a file would have passed through all of them.

## R5. Exit codes

**Decision**: `0` success; `1` wiring failure (job failed, artifacts missing, speakers dropped, no progress); `2` timeout; `3` environment missing (engine or no recordings); `130` interrupted.

**Rationale**: distinct statuses make the check usable from a future hook or task without parsing text. Interruption keeps its conventional code and prints where the child's log is, since the engine keeps running by design.

## R6. Keeping the full-file mode

**Decision**: with no flags the script keeps its current meaning (newest recording, whole file, real destination, `--force` to overwrite), because that is the mode used to validate a real end-to-end result.

**Rationale**: the fix is about making the *quick* path runnable, not about removing the full check. The dangerous flag stays confined to the mode where overwriting is the explicit intent.

## R7. Testability without the engine

**Decision**: extract `pick_recording`, `slice_args`, `build_sample`, `sandbox_paths` and `verdict` as importable functions; the script's `main` only wires them plus the real worker.

**Rationale**: the failure modes worth regression-testing are decisions (isolation, sample length clamping, verdict rules), not the engine run. Those tests run in milliseconds and belong in the suite; the engine run stays a manual quickstart step.
