# Data model: 011-transcription-pc-impact

## PC-use profile

| id | UI label | Threads | Win32 extra priority |
|----|----------|---------|----------------------|
| `usable` | Dejar el PC usable | `max(1, min(4, cpu//2))` | `IDLE_PRIORITY_CLASS` |
| `full` | Usar más CPU (más rápido) | `max(1, cpu-2)` | `BELOW_NORMAL_PRIORITY_CLASS` |

Unknown / empty **config** → `full`.  
Missing field on **old job JSON** → `full`.

## AppConfig

- `transcription_pc_impact: str` (default `"full"`)
- `pc_impact_factory_rev: int` (2 = factory full; missing/1 migrates once to `full`)
- Normalized on load/save like `transcription_preset`

## TranscriptionJob

- `pc_impact: str` captured in `JobStore.enqueue(..., pc_impact=)`
- Retry does not rewrite `pc_impact`

## Child process environment (both profiles)

Set to the resolved thread count: `OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `NUMEXPR_NUM_THREADS`, `TORCH_NUM_THREADS`, plus existing `PYTHONIOENCODING` and `TRANSCRIPTOR_PLAIN`.
