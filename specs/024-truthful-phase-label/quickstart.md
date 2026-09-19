# Quickstart: The notice names the phase that is actually running

## 1. What you should see now

```text
[20:33:36] extracting Preparando audio…
[20:33:36] running    Transcribiendo… 0%
[20:33:38] running    Transcribiendo… 3%
[20:33:52] running    Identificando hablantes… (la fase más lenta) 25%
[20:34:07] running    Identificando hablantes… (la fase más lenta) 50%
[20:34:08] done       Listo 100%
```

Before this feature the same run printed `Audio listo… 4%` and `Audio listo… 35%` while the engine was transcribing.

`Guardando resultados…` covers the stretch after transcription (speakers off) or after the speakers were counted. On a 20 s sample it can pass between two polls and never be shown; on a real meeting it is the label you see just before the row disappears.

## 2. The four phases

| Phase | Engine line that starts it | Label | Engine percentage applies? |
|-------|----------------------------|-------|----------------------------|
| prepare | `- Convirtiendo audio a WAV 16 kHz...` | `Preparando audio…` | no figure yet |
| asr | `> Procesando: …` / `- Transcribiendo (modelo …)` | `Transcribiendo…` | yes |
| speakers | `- Identificando hablantes (diarizacion)...` | `Identificando hablantes… (la fase más lenta)` | no → time-based bar |
| saving | `-> dispositivo: …` / `-> N hablante(s) detectado(s)` | `Guardando resultados…` | no → time-based bar |

`- Audio ya en WAV 16 kHz; se omite reconversión.` starts **no** phase: it reports an action the engine skipped.

## 3. Replay a log by hand

```powershell
$env:PYTHONIOENCODING="utf-8"
.\.venv\Scripts\python.exe -c "from app.transcription.cli_progress import parse_plain_chunk; print(parse_plain_chunk(open(r'RUTA\job.log', encoding='utf-8', errors='replace').read()))"
```

It prints `(label, pct, file, note, phase)` for the whole log; feed it line by line to watch the phase sequence.

## 4. Checks after touching this area

```powershell
$env:PYTHONIOENCODING="utf-8"; $env:QT_QPA_PLATFORM="offscreen"
.\.venv\Scripts\python.exe -m unittest tests.test_cli_progress    # 15 tests, pure text
.\.venv\Scripts\python.exe -m unittest tests.test_batch_tracking  # the worker rule
.\.venv\Scripts\python.exe -m unittest discover -s tests          # whole suite
.\.venv\Scripts\python.exe verify_transcription.py --quick --seconds 20
```

## 5. The thing to remember

Wording lives only in `PHASE_LABELS`, and decisions key off the phase value. The worker used to decide "the percentage does not apply" by looking for the word `hablantes` inside the Spanish label — if you ever feel tempted to read a label to decide something, that is the bug this feature removed.
