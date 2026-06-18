# Contexto para sesiones de desarrollo (Claude Code)

App de escritorio Windows (PySide6) que graba reuniones (video + audio del sistema
+ micrófono → MP4 multipista) y las transcribe automáticamente con el proyecto
hermano **Transcriptor** (`..\Transcriptor`, faster-whisper + pyannote, venv propio;
movido de `Proyectos\Transcriptor` a `Apps\Transcriptor` el jun-11-2026 — la
autodetección en `config.py` prueba ambas ubicaciones).
El README cubre el uso; este archivo documenta lo que NO es obvio desde el código.

## Decisiones de arquitectura (no revertir sin razón)

- **Transcripción = subproceso CLI + cola persistente** (no librería, no venv
  fusionado). Cada proyecto conserva su `.venv` (ambos Python 3.11.9). Se evaluaron
  y descartaron: venv unificado (acopla torch/pyannote a la app; pyannote ya rompió
  API 3.x→4.x) y worker con Tarea Programada (sobre-ingeniería para un usuario).
- **stdout del subproceso va a un ARCHIVO de log, nunca a un pipe**: por eso el
  hijo sobrevive al cierre de la app. El éxito se decide por exit code + existencia
  de archivos; el parseo del log es solo progreso cosmético.
- **La grabación siempre manda**: el worker no arranca jobs si `is_recording()`, y
  suspende el proceso (`psutil.suspend/resume`) si una grabación empieza a mitad.
  Además `BELOW_NORMAL_PRIORITY_CLASS` + `--threads cpu-2`.
- **Sin LLM**: el usuario pidió explícitamente NO integrar modelos para minutas.
  El `transcripcion.json` (bloques hablante/tiempos) queda como interfaz si algún
  día cambia de opinión.
- **Pantalla completa = WGC del monitor** (`WindowsScreenCapture`, fallback gdigrab).
  gdigrab por CPU da ~18 fps en un monitor de 3440×1440 → video con frames
  duplicados percibido como "lag/desincronización" (bug resuelto jun-2026).

## Trampas conocidas (cosas que ya mordieron)

- **El muxer MP4 descarta `-metadata:s:a:N title=`**: el nombre visible de una pista
  MP4 vive en el átomo hdlr (`handler_name`). `mux_recording` escribe AMBOS.
  Grabaciones anteriores a jun-10-2026 no tienen nombres de pista → la extracción
  cae al fallback `amix` (correcto). La pista "Mezcla" es la que se transcribe.
- **`convertir_a_wav16k` del Transcriptor no usa `-map`**: jamás pasarle el MP4
  multipista directo (ffmpeg elegiría solo "Sistema" y se pierde la voz del usuario).
  Siempre pre-extraer con `extract_audio_for_transcription`.
- **Sin token HF, el Transcriptor termina con exit 0 y sin hablantes** (degrada en
  silencio). Validar leyendo el campo `hablantes` de `transcripcion.json`.
- **Rutas con espacios** (la app puede vivir en carpetas con espacios, p. ej. dentro
  de OneDrive): subprocesos SIEMPRE con lista de argumentos, nunca `shell=True`.
- **OneDrive**: cola/logs/WAVs de trabajo van a `%LOCALAPPDATA%` (fuera del sync).
  Los `.venv` están pinneados (`attrib +P`) para que Files On-Demand no deshidrate
  las DLLs de torch.
- **Python 3.14 es el default de `py`**: para venvs nuevos usar `py -3.11`
  (torch/ctranslate2 validados en 3.11.9).
- **mpdecimate sobre pantalla estática da pocos frames únicos POR DISEÑO** (WGC solo
  emite callbacks cuando el contenido cambia): para medir frescura de captura, poner
  una animación en pantalla (p. ej. `ffplay -f lavfi testsrc2`).
- **Tests headless de UI**: construir `MainWindow` SIN `show()` (show arranca el
  AudioMonitor que abre dispositivos reales) con `QT_QPA_PLATFORM=offscreen` y
  `PYTHONIOENCODING=utf-8`.
- **Callbacks del Recorder corren en hilos daemon**, no en el hilo Qt: todo pasa
  por señales (`_tx_update_sig`, etc.). El encolado en `_on_finished` debe ocurrir
  ANTES del check de `_quit_after_finalize` (la app puede morir justo después).

## Rendimiento medido (laptop sin GPU dedicada)

- Transcripción ≈ **2–2.5× la duración del audio**; la fase lenta es la diarización
  (embeddings: 1h13m para una reunión de ~1h).
- gdigrab pantalla 3440×1440: ~18 fps máx (por eso WGC). WGC: 30 fps de contenedor
  con ~27 fps reales de contenido.
- GPU: detección automática por ejecución (`device: auto` en config.yaml del
  Transcriptor, vía `ctranslate2.get_cuda_device_count`). La diarización usará GPU
  cuando se instale torch CUDA (el `pipeline.to(cuda)` ya está).

## Verificación rápida

```powershell
# Integración de transcripción end-to-end en <1 min (cola temporal aislada):
.\.venv\Scripts\python.exe verify_transcription.py --quick

# Pipeline de grabación (graba clips reales de 3-7 s):
.\.venv\Scripts\python.exe verify_pipeline.py

# Entorno:
.\.venv\Scripts\python.exe smoke_test.py
```

Estado de la cola real: `%LOCALAPPDATA%\MeetingRecorder\transcripts\queue\*.json`
(logs por job en `...\transcripts\logs\`). Config de la app:
`%APPDATA%\MeetingRecorder\config.json`.

## Transcriptor (proyecto hermano)

- `requirements.lock.txt` = entorno congelado validado (torch **+cpu**: reinstalar
  SIEMPRE con `--index-url https://download.pytorch.org/whl/cpu` ANTES del resto).
- Cambios hechos desde aquí: `device: auto` (asr.py + diarize.py + config.yaml),
  modo `TRANSCRIPTOR_PLAIN=1` (progreso parseable sin rich). Su CLI manual y sus
  `.bat` no cambiaron.
- No es instalable como paquete (sin pyproject.toml) — irrelevante para la
  integración por subproceso.
- Su `.venv` fue MOVIDO de carpeta junto con el proyecto: `python.exe` y los
  imports funcionan (pyvenv.cfg apunta al Python base, que no cambió), pero los
  lanzadores `Scripts\*.exe` (pip.exe, etc.) tienen la ruta vieja embebida —
  usar `python -m pip` en vez de `pip` dentro de ese venv.
