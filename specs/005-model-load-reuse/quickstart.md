# Quickstart: Model-Load Reuse (when implemented)

## Today (deferred)

No product change. Transcription still cold-starts per job via sibling CLI.

## Future measurement

1. Pick a short WAV (~30–60 s) and preset Equilibrado.
2. Run job A (cold): note wall time from process start → first ASR progress line in job log.
3. With warm worker up, run job B same preset: same metric.
4. Expect B model-init ≪ A; total wall clock should drop.
5. Start a recording while warm worker idle/busy → confirm no new job starts / child suspends per Recording Always Wins.
