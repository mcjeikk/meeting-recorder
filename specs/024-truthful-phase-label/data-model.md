# Data Model: The notice names the phase that is actually running

Nothing is persisted. These values live for one poll of the log.

## Phase

| Value | Meaning | Engine line that starts it | Label |
|-------|---------|----------------------------|-------|
| `prepare` | converting the audio to 16 kHz WAV | `- Convirtiendo audio a WAV 16 kHz...` | `Preparando audio…` |
| `asr` | transcribing | `> Procesando: <file>` and `- Transcribiendo (modelo …, idioma …)...` | `Transcribiendo…` |
| `speakers` | identifying speakers | `- Identificando hablantes (diarizacion)...` | `Identificando hablantes… (la fase más lenta)` |
| `saving` | merging and writing the outputs | `-> dispositivo: …` (transcription returned) or `-> N hablante(s) detectado(s)` or the diarization-failed warning | `Guardando resultados…` |

### Invariants

- **INV-1**: `Audio ya en WAV 16 kHz` starts no phase: it reports an action that was skipped.
- **INV-2**: A phase is never entered after the engine reported it finished (the device line ends `asr`, the speaker count ends `speakers`).
- **INV-3**: A line matching nothing leaves phase and label unchanged.
- **INV-4**: Within one chunk the last phase wins; a `> Procesando:` in the chunk also switches the live file and resets the percentage.
- **INV-5**: The label is derived from the phase in exactly one place; nothing reads the label to make a decision.

## Percentage applicability

| Phase | Engine percentage applies? | Emitted `pct` |
|-------|---------------------------|---------------|
| `prepare` | no figure exists yet | unchanged |
| `asr` | yes — `transcribiendo... NN%` | the parsed number (0 on file switch) |
| `speakers` | no (the engine prints nothing for hours) | `-1` = indeterminate |
| `saving` | no | `-1` = indeterminate |

### Invariants

- **INV-6**: `PHASES_WITHOUT_ASR_PERCENT = {speakers, saving}` is the single statement of this rule; the worker compares phases against it.
- **INV-7**: Indeterminate means "the app's time-based estimate drives the bar" (spec 021), never "reuse the previous figure".

## Parse result

| Field | Before | After |
|-------|--------|-------|
| stage | Spanish label or None | unchanged (now derived from the phase) |
| pct | number, 0 on file switch, -1 indeterminate, None if no news | unchanged |
| cli_name | file the engine announced | unchanged |
| nota | `sin hablantes` on silent degradation | unchanged |
| phase | — | new: one of the four values, or None when the chunk said nothing |

### Invariants

- **INV-8**: The four existing fields keep their meaning and order, so the worker's unpacking and every existing test stay valid.
- **INV-9**: `phase is None` and `stage is None` always agree: either the chunk announced a phase or it did not.
