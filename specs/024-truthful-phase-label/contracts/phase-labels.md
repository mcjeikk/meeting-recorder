# Contract: phases and labels read from the engine log

Extends `specs/020-batch-queue-tracking/contracts/cli-progress-log.md`. The engine is unchanged; this is how the Recorder reads it.

## API

```python
PHASE_PREPARE = "prepare"
PHASE_ASR = "asr"
PHASE_SPEAKERS = "speakers"
PHASE_SAVING = "saving"
PHASES_WITHOUT_ASR_PERCENT = frozenset({PHASE_SPEAKERS, PHASE_SAVING})

PHASE_LABELS: dict[str, str]          # phase -> Spanish label (the only place wording lives)
label_for_phase(phase) -> str

parse_plain_chunk(texto) -> (stage, pct, cli_name, nota, phase)
```

## Matching rules

| # | Engine line | Phase | pct |
|---|-------------|-------|-----|
| P-1 | `> Procesando: <file>` | `asr` | `0` (new file, previous figure is void) |
| P-2 | `- Convirtiendo audio a WAV 16 kHz...` | `prepare` | unchanged |
| P-3 | `- Audio ya en WAV 16 kHz; se omite reconversión.` | **none** | unchanged |
| P-4 | `- Transcribiendo (modelo …, idioma …)...` | `asr` | unchanged |
| P-5 | `    transcribiendo... NN%` | `asr` | `NN` |
| P-6 | `    -> dispositivo: <dev>` | `saving` | `-1` |
| P-7 | `- Identificando hablantes (diarizacion)...` | `speakers` | `-1` |
| P-8 | `    -> N hablante(s) detectado(s)` | `saving` | `-1` |
| P-9 | `[!] La diarizacion no se completo (…)` | `saving` | `-1`, plus nota `sin hablantes` |
| P-10 | `Diarizacion solicitada pero no hay …` | `saving` | `-1`, plus nota `sin hablantes` |
| P-11 | `OK en Ns -> <carpeta>` | **none** | unchanged (completion is decided by the transcript existing, spec 020) |
| P-12 | anything else | **none** | unchanged |

- **C-1**: Within a chunk, later matches override earlier ones; the last phase in the chunk is returned.
- **C-2**: `stage` is always `label_for_phase(phase)`; when no phase matched, both are `None`.
- **C-3**: The device value is not used to change the label (a GPU run is visible in the log).
- **C-4**: The five-field result keeps the first four fields in their current order and meaning.

## Worker rules

- **W-1**: A returned phase replaces the remembered phase; `None` leaves it alone.
- **W-2**: When the current phase is in `PHASES_WITHOUT_ASR_PERCENT`, the engine percentage does not apply and the bar is driven by the time-based estimate (`pct = -1`).
- **W-3**: The worker MUST NOT inspect label text to make any decision.
- **W-4**: `⏸ En pausa (grabando)…` is emitted by the worker and takes precedence over any phase label.
- **W-5**: Promoting the next file in a batch resets the phase to `asr` and the percentage to 0, as today.

## Non-goals

- No change to the engine's messages, its `.bat` files or its configuration.
- No UI layout change: same notice, same queue row, different words in them.
