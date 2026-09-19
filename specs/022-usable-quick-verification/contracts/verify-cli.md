# Contract: `verify_transcription.py` command line

Maintenance check of the Recorder → Transcriptor integration. Runs the app's own queue, worker and engine subprocess; it is not a unit test and not a quality benchmark.

## Usage

```text
python verify_transcription.py                      # full: newest recording, whole file, real destination
python verify_transcription.py "C:\ruta\video.mp4"  # full, on a specific recording
python verify_transcription.py --quick               # sandbox: 60 s sample, with speakers
python verify_transcription.py --quick --no-speakers # sandbox: 60 s sample, fastest wiring check
python verify_transcription.py --quick --seconds 30  # shorter sample
python verify_transcription.py --force               # full mode only: overwrite an existing transcript
python verify_transcription.py --timeout 900         # give up after N seconds
```

## Rules

- **V-1**: `--quick` always uses a sandbox: its own queue, logs, work folder, speed history and destination. It never resolves a path inside the user's output folder and never asks for `--force`.
- **V-2**: `--force` is accepted only in full mode; combined with `--quick` it is refused with an explanatory error, because the sandbox cannot collide with user data.
- **V-3**: `--seconds` is clamped to the source length; a source shorter than the request is used whole.
- **V-4**: The sample is produced by stream copy with every stream mapped, so audio-track names and layout survive.
- **V-5**: Subprocesses are launched with argument lists only.
- **V-6**: On success the sandbox is deleted; on any failure it is kept and its path plus the engine log path are printed.
- **V-7**: The engine is never modified or reconfigured; the check only reads where the sibling project lives.

## Verdict

A run passes when **all** hold:

1. the job reached the completed state;
2. `transcripcion.txt`, `transcripcion.srt` and `transcripcion.json` exist in the run's destination;
3. at least one progress update named the sampled media;
4. at least one update carried a finish-time estimate;
5. with speakers requested, the structured result reports ≥ 1 speaker.

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Pass |
| 1 | Wiring failure: job failed, artifacts missing, no progress updates, or speakers dropped |
| 2 | Timeout |
| 3 | Environment: sibling engine unavailable, no recording to sample, or sample could not be produced |
| 130 | Interrupted by the user (the engine child may still be running; its log path is printed) |

## Output

Human-readable, one line per event plus a final verdict block naming: the sampled recording, sample seconds, elapsed time, artifacts found, speakers found, and — on failure — the reason and where to look.
