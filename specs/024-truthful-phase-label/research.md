# Research: The notice names the phase that is actually running

## R1. What the engine actually prints (the authority)

From `Transcriptor/transcribe.py::procesar_archivo` in plain mode (`TRANSCRIPTOR_PLAIN=1`), per file, in order:

```text
> Procesando: <archivo>.wav
  - Audio ya en WAV 16 kHz; se omite reconversión.      # or: - Convirtiendo audio a WAV 16 kHz...
  - Transcribiendo (modelo large-v3-turbo, idioma es)...
    transcribiendo... 24%                               # only on jumps of >=10 points
    transcribiendo... 61%
    transcribiendo... 93%
    -> dispositivo: cpu                                 # printed AFTER transcription returned
  - Identificando hablantes (diarizacion)...
    -> 1 hablante(s) detectado(s)                       # or: [!] La diarizacion no se completo (...)
  OK en 32s  ->  <carpeta>
      - transcripcion.txt
```

**Finding**: every phase is announced *before* it runs, except the device line, which is printed *after* transcription ended. The announcements are the reliable signal; the percentages are sparse.

## R2. Why the label went stale

`parse_plain_chunk` matches `Convirtiendo audio`, `Audio ya en WAV`, `transcribiendo... NN%`, `-> dispositivo: cuda` and `Identificando hablantes`. The line `- Transcribiendo (modelo …)` is not matched at all.

Consequence: after `Audio ya en WAV` sets the label to `Audio listo…`, nothing replaces it until a percentage line appears. Percentages come from a callback that only prints on jumps of ≥10 points, so:

| Case | What the user saw |
|------|-------------------|
| 20 s sample, no speakers | `Audio listo… 5%` then `Audio listo… 35%` (observed 2026-09-18) |
| 20 s sample, speakers | `Audio listo… 4%`, then straight to `Identificando hablantes…` |
| A file whose ASR never emits a jump | `Audio listo…` for the whole transcription |

**Decision**: match the announcement (`- Transcribiendo (modelo`) and stop treating `Audio ya en WAV` as a phase. It is not an action — it is the engine noting that it skipped an action.

## R3. The device line

`-> dispositivo: cuda` currently relabels to `Transcribiendo (GPU)…`. Since the engine prints it after `transcribir()` returns, the label asserts a phase that has just finished; and the next announcement (speakers) follows within milliseconds, so the GPU label is effectively unreachable *and* wrong when reached.

**Decision**: the device stops driving the label. It is used as the boundary "transcription finished" → the results phase.

**Alternatives considered**:

| Option | Why rejected |
|--------|----------------|
| Keep `Transcribiendo (GPU)…` | States a finished phase as current |
| Show the device as a permanent badge in the UI | Real feature, different scope; nothing today asks for it |
| Parse the device and stash it in the job note | The note is user-facing and reserved for degradations ("sin hablantes") |

## R4. The unnamed final stretch

After the device line (speakers off) or after `-> N hablante(s) detectado(s)`, the engine merges words with speaker turns, builds blocks, and writes three files. Today the label still says `Identificando hablantes… (la fase más lenta)`.

**Decision**: a fourth phase, labelled `Guardando resultados…`. Short in wall-clock terms, but it is the honest answer for the gap between "speakers found" and the row disappearing.

## R5. Phase as a value, not as text

`worker._monitor` contains:

```python
elif nuevo_stage and "hablantes" in nuevo_stage.lower():
    pct = -1
```

That is progress behavior keyed on the Spanish label. Rewording the notice would silently change how the bar behaves (this is the same class of coupling that kept the bar frozen at 90 % before spec 021).

**Decision**: `parse_plain_chunk` returns an explicit phase (`prepare` / `asr` / `speakers` / `saving`), the label is a lookup from that phase, and the worker keys its decision on the phase. The parse result grows one field; the four existing fields keep their meaning.

**Rationale**: it makes FR-006 structural rather than a promise, and it lets the "percentage does not apply here" rule be stated once (`PHASES_WITHOUT_ASR_PERCENT`).

## R6. What must not move

| Behavior | Guarded by |
|----------|------------|
| `> Procesando:` switches the live file and resets the percentage to 0 | `tests/test_cli_progress.py::test_file_switch_resets_percent`, `tests/test_batch_tracking.py` |
| Speaker identification makes the percentage indeterminate | `test_diarization_clears_asr_percent`, `test_batch_tracking` |
| "sin hablantes" note on silent degradation | `parse_plain_chunk` nota, `worker._check_speakers` |
| Per-file sections for errors and OOM | `log_section_for`, `error_in_section`, `section_ended_in_diarization` |
| The pause label wins over any phase | `worker._monitor` emits `⏸ En pausa (grabando)…` directly |

**Decision**: the phase addition must not touch any of these paths; only the label source and the `pct = -1` rule change.

## R7. Out of scope

- A GPU/CPU indicator in the UI.
- Reporting progress *within* speaker identification (the engine prints nothing; spec 021's time-based bar already covers it).
- Any change to the engine, its wording or its `.bat` scripts.
