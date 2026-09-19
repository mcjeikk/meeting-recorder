# Quickstart: A quick check that can actually be run

## 1. The command

```powershell
cd "...\Apps\Recorder"
.\.venv\Scripts\python.exe verify_transcription.py --quick
```

Measured on the audited laptop (20 s sample of a real meeting):

| Variant | Time | What it proves |
|---------|------|----------------|
| `--quick --no-speakers --seconds 20` | 22 s | queue, extraction of the "Mezcla" track, engine subprocess, progress, finish-time estimate, artifacts |
| `--quick --seconds 20` | 32 s | the above plus speaker identification really produced speakers |
| `--quick` (60 s sample, speakers) | ~1–2 min | same, on a longer sample |

## 2. What a pass looks like

```text
Muestra de 20s de 1er reunion arq empresarial christian braatz.mp4 → sandbox C:\...\Temp\verify_tx_n2xa0jg2
Verificando 1er reunion ... [muestra 20s].mp4 (con hablantes)
[20:03:12] pending    En cola
[20:03:12] extracting Preparando audio…
[20:03:15] running    Audio listo… 4%
[20:03:28] running    Identificando hablantes… (la fase más lenta) 25%
[20:03:42] done       Listo 100%

OK en 32s — cableado completo verificado
  Artefactos:   transcripcion.txt, transcripcion.srt, transcripcion.json
  Avances:      7 del archivo, 3 con hora estimada
  Hablantes:    1
```

On a pass the sandbox is deleted. On any failure it is kept and its path is printed together with the engine log.

## 3. Checks to run after touching this area

```powershell
$env:PYTHONIOENCODING="utf-8"
.\.venv\Scripts\python.exe -m unittest tests.test_verify_quick        # 18 tests, no engine
.\.venv\Scripts\python.exe verify_transcription.py --quick --seconds 20
```

Then confirm nothing of yours moved:

```powershell
Get-ChildItem "$env:LOCALAPPDATA\MeetingRecorder\transcripts" -Force | Select-Object Name, LastWriteTime
Get-ChildItem "$env:TEMP" -Filter "verify_tx_*"      # must print nothing after a pass
```

## 4. Reading a failure

| Message | Meaning |
|---------|---------|
| `el trabajo terminó en estado 'error'` | the engine failed; the printed log has the reason |
| `faltan artefactos: ...` | it transcribed but did not write everything the app expects |
| `no llegó ningún avance del archivo verificado` | the worker never reported this file — spec 020 wiring broken |
| `no llegó ninguna hora estimada de término` | spec 021 wiring broken (no `eta_epoch` reached the UI) |
| `se pidieron hablantes y el resultado no trae ninguno` | silent speaker degradation — usually the missing HuggingFace token |
| `No encuentro el Transcriptor con su venv en: ...` | environment, not wiring: the sibling project or its `.venv` moved |

## 5. Full mode is still there

```powershell
.\.venv\Scripts\python.exe verify_transcription.py "C:\ruta\reunion.mp4" --force
```

Whole file, real destination, hours of work. `--force` only exists there, and `--quick --force` is refused on purpose.
