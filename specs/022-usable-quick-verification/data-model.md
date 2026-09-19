# Data Model: A quick check that can actually be run

Nothing is persisted by this feature. The entities below exist only for the duration of one verification run.

## Verification run

| Field | Meaning | Rules |
|-------|---------|-------|
| mode | `quick` or `full` | `quick` samples a slice into a sandbox; `full` transcribes the whole recording into the real destination |
| source recording | the real media being sampled | newest `.mp4` in the configured output folder unless a path is given |
| sample seconds | requested slice length | default 60; clamped to the recording's own length |
| speakers | whether speaker identification runs | off in the fast variant, on when requested |
| sandbox | one temp folder holding `queue/`, `logs/`, `work/`, `speed.json` and the destination | created per run; removed on success, kept on failure |
| updates seen | progress snapshots received from the worker | must include at least one naming the sample, and one carrying a finish-time estimate |
| artifacts | files found in the destination | `transcripcion.txt`, `transcripcion.srt`, `transcripcion.json` |
| speakers found | count reported in the structured result | required ≥ 1 when speakers were requested |
| verdict | pass / fail with a reason, plus an exit status | see the exit-code table in contracts |

### Invariants

- **INV-1**: A verification run never resolves a destination inside the user's output folder in `quick` mode.
- **INV-2**: A verification run never writes the machine's real speed history.
- **INV-3**: A run that produces artifacts but no progress updates is a failure.
- **INV-4**: A run with speakers requested and zero speakers reported is a failure.
- **INV-5**: The sandbox survives a failure (for diagnosis) and is removed after a pass.
- **INV-6**: The check never deletes or overwrites anything outside its sandbox — in `full` mode overwriting requires the explicit existing flag.

## Sample

| Field | Meaning | Rules |
|-------|---------|-------|
| path | the slice written inside the sandbox | named after the source with a marker, so the engine's own logs are readable |
| tracks | audio layout copied from the source | must be preserved (stream copy), because track selection is part of what is verified |
| duration | actual length of the slice | ≤ requested seconds; equals the source when the source is shorter |
