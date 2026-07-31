# Contract: CLI preset mapping (Recorder → Transcriptor)

**Feature**: `002-transcription-speed-presets` | **Date**: 2026-07-27

## Invocation shape (unchanged host)

```
<transcriptor_venv>/python.exe -u -X utf8 transcribe.py <wav>
  --language <lang>
  --output <abs_out_dir>
  --threads <cpu_count-2>
  [--model <name>]
  [--beam-size <n>]
  [--no-diarize]
```

Always argv list (never shell string). Env: `TRANSCRIPTOR_PLAIN=1`, `PYTHONIOENCODING=utf-8`. Priority: below-normal + existing suspend-on-record.

## Mapping

| Job.preset | Extra argv |
|------------|------------|
| `rapido` | `--model large-v3-turbo --beam-size 5 --no-diarize` |
| `equilibrado` | `--model large-v3-turbo --beam-size 5` |
| `maxima_calidad` | `--model large-v3 --beam-size 5` |

If `job.no_diarize` is true for any reason (preset or degraded retry), `--no-diarize` MUST appear once.

## Success / failure

Unchanged: exit code + presence of result artifacts; log file cosmetic. Rápido jobs MUST NOT be treated as failure solely because `hablantes` is empty/absent.

## Phase 2 note

If a warm sibling worker is added later, this contract may gain a transport (socket/named pipe) but MUST preserve semantic equivalence of the three preset mappings and separate environments.
