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
  hijo sobrevive al cierre de la app. El éxito se decide por existencia de
  `transcripcion.txt` (en un CLI con varios WAV el exit code es global); el
  parseo del log es solo progreso cosmético. Jobs pendientes compatibles
  (idioma/modelo/beam/hablantes/`output_base`) van en un solo argv; Whisper y
  pyannote se cachean dentro de ese proceso del Transcriptor, no en el Grabador.
- **En un lote solo UN job está `running`**: el que el CLI está procesando de
  verdad (`> Procesando:` → `cli_progress.job_for_cli_name`); el resto del argv
  queda `pending` hasta su turno. Cada poll cosecha los que ya tienen
  `transcripcion.txt` (`_harvest_ready`), sin esperar a que salga el proceso.
  Marcar los N como `running` hacía que la lista mostrara todo "en curso", el
  aviso se quedara en el primer archivo y su % (bug sep-2026).
- **El log del lote se lee POR SECCIONES** (`log_section_for`): el error o el
  fallo de diarización de un archivo no debe degradar ni marcar como fallidos a
  los demás. Sección vacía = ese archivo nunca empezó (se reintenta tal cual).
- **La grabación siempre manda**: el worker no arranca jobs si `is_recording()`, y
  suspende el proceso (`psutil.suspend/resume`) si una grabación empieza a mitad.
  Además el job lleva un **Uso del PC** (`full` por defecto: `--threads cpu-2`
  + BELOW_NORMAL; `usable`: pocos hilos + IDLE). `--threads` solo no basta:
  hay que topar también OpenMP/torch o la diarización satura todos los núcleos.
- **Sin LLM**: el usuario pidió explícitamente NO integrar modelos para minutas.
  El `transcripcion.json` (bloques hablante/tiempos) queda como interfaz si algún
  día cambia de opinión.
- **Pantalla completa = WGC del monitor** (`WindowsScreenCapture`, fallback gdigrab).
  gdigrab por CPU da ~18 fps en un monitor de 3440×1440 → video con frames
  duplicados percibido como "lag/desincronización" (bug resuelto jun-2026).
- **Preview WGC idle tumba pythonw en Intel** (`igd10um64xe.DLL`, WER 2026-09-08
  y de nuevo 2026-09-11 00:21 *después* de que el job ya había terminado). El
  timer de ~1.5 s no debe llamar `grab_*_frame`; solo un grab puntual al cambiar
  fuente/Actualizar. La preview de grabación usa el frame del backend, no una
  sesión WGC extra.

## Trampas conocidas (cosas que ya mordieron)

- **El muxer MP4 descarta `-metadata:s:a:N title=`**: el nombre visible de una pista
  MP4 vive en el átomo hdlr (`handler_name`). `mux_recording` escribe AMBOS.
  Grabaciones anteriores a jun-10-2026 no tienen nombres de pista → la extracción
  cae al fallback `amix` (correcto). La pista "Mezcla" es la que se transcribe.
- **`convertir_a_wav16k` del Transcriptor no usa `-map`**: jamás pasarle el MP4
  multipista directo (ffmpeg elegiría solo "Sistema" y se pierde la voz del usuario).
  Siempre pre-extraer con `extract_audio_for_transcription`. Si el WAV de trabajo
  ya es 16 kHz mono PCM, `preparar_wav16k` no lo reconvierte.
- **OOM no empieza por Rápido**: `apply_oom_degrade` pasa a turbo + PC usable
  **con hablantes**; `no_diarize` es el último recurso (nota visible). Rápido
  sigue siendo la elección explícita del usuario.
- **Sin token HF, el Transcriptor termina con exit 0 y sin hablantes** (degrada en
  silencio). Validar leyendo el campo `hablantes` de `transcripcion.json` — que es
  un **mapa** `{SPEAKER_00: …}`, no una lista (contarlo mal da falsos negativos).
- **El log anuncia cada fase ANTES de hacerla, menos `-> dispositivo:`**, que se
  imprime DESPUÉS de transcribir. De ahí la tabla de fases de `cli_progress.py`
  (spec 024): `Convirtiendo audio`→preparar, `- Transcribiendo (modelo`→ASR,
  `Identificando hablantes`→hablantes, `-> dispositivo:` y `-> N hablante(s)`→
  guardar. `Audio ya en WAV` NO es fase (es una acción omitida): tomarla por tal
  mostraba "Audio listo… 35%" mientras transcribía. El % del CLI solo aplica en
  ASR; en el resto manda la estimación por tiempo (`PHASES_WITHOUT_ASR_PERCENT`).
  Regla: **ninguna decisión se toma leyendo el texto en español de la etiqueta**.
- **Hablantes = exclusive de community-1** (`pipeline/diarize.py`): no usar
  `speaker_diarization` (permite solapes y ensucia el merge con Whisper en
  español). pyannote **4.0.7** (mismo modelo; no hay community-2).
- **Rutas con espacios** (la app puede vivir en carpetas con espacios, p. ej. dentro
  de OneDrive): subprocesos SIEMPRE con lista de argumentos, nunca `shell=True`.
- **OneDrive**: cola/logs/WAVs de trabajo van a `%LOCALAPPDATA%` (fuera del sync).
  Los `.venv` están pinneados (`attrib +P`) para que Files On-Demand no deshidrate
  las DLLs de torch.
- **`_cleanup_wav` puede fallar en silencio** (handle del CLI, antivirus) y esos
  WAV de 16 kHz son cientos de MB: la reconciliación al arrancar pasa
  `purge_orphan_work_dirs()` sobre `transcripts\work\` (se encontraron 468 MB
  colgados de jobs terminados en sep-2026).
- **Python 3.14 es el default de `py`**: para venvs nuevos usar `py -3.11`
  (torch/ctranslate2 validados en 3.11.9).
- **mpdecimate sobre pantalla estática da pocos frames únicos POR DISEÑO** (WGC solo
  emite callbacks cuando el contenido cambia): para medir frescura de captura, poner
  una animación en pantalla (p. ej. `ffplay -f lavfi testsrc2`).
- **Tests headless de UI**: construir `MainWindow` SIN `show()` (show arranca el
  AudioMonitor que abre dispositivos reales) con `QT_QPA_PLATFORM=offscreen` y
  `PYTHONIOENCODING=utf-8`. Combos: `StrongFocus` + `scroll_guard` (la rueda no
  muta un desplegable sin foco; si no, el scroll de la ventana cambia calidad/mic).
- **UI = paneles oscuros + Grabar verde** (`app/ui/main_window.py`, `_STYLE`):
  GroupBoxes numerados, botón ● Grabar / ■ Detener. Combos: `StrongFocus` +
  `scroll_guard` (la rueda no muta un desplegable sin foco).
- **Callbacks del Recorder corren en hilos daemon**, no en el hilo Qt: todo pasa
  por señales (`_tx_update_sig`, etc.). El encolado en `_on_finished` debe ocurrir
  ANTES del check de `_quit_after_finalize` (la app puede morir justo después).

## Rendimiento medido (laptop sin GPU dedicada)

- Transcripción (con hablantes) ≈ **1.08× la duración del audio** con "Usar más CPU"
  y ≈ **1.45× "Dejar el PC usable"** — medido sep-2026 sobre 22 reuniones reales
  (`duracion_seg` del `transcripcion.json` vs `OK en Ns` del log; n=18 y n=2,
  rango 1.00–1.89×). El viejo "2–2.5×" y el "1h13m de diarización para 1h de
  audio" estaban al doble de la realidad: no usarlos para estimar.
- La estimación en vivo vive en `app/transcription/eta.py` y **aprende** de esta
  máquina: `%LOCALAPPDATA%\MeetingRecorder\transcripts\speed.json` guarda
  (duración de audio, tiempo activo) por `modelo|hablantes|uso del PC`; con ≥3
  muestras manda la mediana propia, antes el default medido. El tiempo se cuenta
  ACTIVO (suspender por grabación no consume la estimación).
- **La carga de modelos se cobra UNA VEZ por ejecución del CLI**, no por archivo
  (`STARTUP_SECONDS`, 12 s; spec 025): solo el primer archivo del argv la espera,
  y un job re-adoptado entra en un proceso que ya la pagó. Medida el 18-sep-2026
  con 45 s de audio y la misma configuración: 55 s y 54 s cargando contra 42 s
  reutilizando → 12–13 s. Con el viejo 40 s por archivo, el "lote listo ~HH:MM"
  de 10 archivos inventaba 6 minutos y cada archivo prometía 40 s de más (medido:
  370 s prometidos contra 313 s y 330 s reales en muestras de 5 min). Si algún día
  se mide en frío o en un disco lento, este es el número a repetir — no a adivinar.
- gdigrab pantalla 3440×1440: ~18 fps máx (por eso WGC). WGC: 30 fps de contenedor
  con ~27 fps reales de contenido.
- GPU: detección automática por ejecución (`device: auto` en config.yaml del
  Transcriptor, vía `ctranslate2.get_cuda_device_count`). La diarización usará GPU
  cuando se instale torch CUDA (el `pipeline.to(cuda)` ya está).

## Revisar una cola que corrió sin nadie delante

**Lo que la ventana muestra ya no se olvida** (spec 026): cada estado emitido
(`_emit`) y cada decisión del worker (arranque del CLI con su lote, cambio de
archivo en curso, cosecha, pausa/reanudación por grabación, degradación por OOM,
reintento, fallo, desenlace, velocidad aprendida) se anotan en
`%LOCALAPPDATA%\MeetingRecorder\transcripts\events.jsonl` (una línea JSON; rota
a `.1` a los 8 MB). Es **solo diagnóstico**: nadie lo lee para decidir nada y
todos sus errores se tragan — el rastro nunca puede arruinar una transcripción.

```powershell
.\.venv\Scripts\python.exe tools\night_report.py            # resumen por archivo
.\.venv\Scripts\python.exe tools\night_report.py --hours 10 # solo la última noche
.\.venv\Scripts\python.exe tools\night_report.py --raw      # + cada decisión
```

El informe da, por archivo: fases mostradas, desenlace, cuánto tardó, cuánto
prometía la estimación y el factor aprendido. **No marca desvíos de estimación en
archivos de menos de 2 minutos**: ahí manda el piso de 60 s del estimado y el
porcentaje no significa nada (hallazgo F2 de la spec 025).

Este rastro se pagó solo en su primer lote real: destapó un `PermissionError` al
guardar un registro de la cola que marcaba el job como fallido. Dos hilos (Qt y
worker) guardaban el mismo job con un temporal de nombre fijo. Arreglado en la
spec 027: temporal por proceso+hilo, reintento corto al guardar Y al leer, y
"no existe" se responde al instante (reintentarlo haría pasar por ausente un
registro ocupado, que es como se cuela un duplicado en la cola).

## Verificación rápida

```powershell
# Integración end-to-end sobre una MUESTRA de la última grabación, en sandbox
# (cola, logs, WAVs, historial de velocidad y destino desechables: no toca tus
# transcripciones). Con hablantes ~35 s; --no-speakers ~20 s. Falla si no llegan
# avances, no llega hora estimada o se pidieron hablantes y vinieron 0:
.\.venv\Scripts\python.exe verify_transcription.py --quick
.\.venv\Scripts\python.exe verify_transcription.py --quick --no-speakers --seconds 20

# Pipeline de grabación (graba clips reales de 3-7 s):
.\.venv\Scripts\python.exe verify_pipeline.py

# Entorno:
.\.venv\Scripts\python.exe smoke_test.py
```

Estado de la cola real: `%LOCALAPPDATA%\MeetingRecorder\transcripts\queue\*.json`
(logs por job en `...\transcripts\logs\`). Config de la app:
`%APPDATA%\MeetingRecorder\config.json`.

**El histórico se poda al arrancar** (`retention.py`, spec 023): los terminados
duran 30 días y como máximo 200, con tope de 100 borrados por pasada; pendientes,
en curso, fallidos y cancelados NO se tocan (esos los limpia el usuario). Importa
porque `JobStore.all()` relee y parsea TODOS los JSON y es el sustrato de casi
toda pregunta (~0,06 ms por registro y por consulta: 2 ms con 31, 37 ms con 600).
Consecuencia a no olvidar: **el registro `done` ya no es quien recuerda que un
archivo se transcribió** — sin registro, `classify_import` lo pregunta al disco
(`transcript_exists`: `transcripcion.txt` en el destino). Si alguna vez se poda
también por otro criterio, esa comprobación es la que evita repetir horas de CPU.

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

<!-- SPEC-KIT:BEGIN (managed by the spec-kit skill — do not edit inside this block) -->
## Spec-Driven Development (Spec Kit)

This project uses **Spec-Driven Development (SDD)** via [GitHub Spec Kit](https://github.com/github/spec-kit). The spec is the source of truth: intent is captured and agreed *before* code, so implementation is the mechanical step of satisfying an approved spec rather than guesswork.

**Adopt this workflow by default for any non-trivial feature, change, or bugfix** (anything beyond a one-line edit or a quick question). Do not jump straight to code. Drive it through the installed Spec Kit commands, in order:

1. `/speckit.constitution` — establish or update the project's non-negotiable principles (run once per project, revisit when principles change).
2. `/speckit.specify` — turn the request into a feature spec (the *what* and *why*, no tech choices). Creates `specs/<nnn-feature>/spec.md`.
3. `/speckit.clarify` — resolve underspecified areas with targeted questions **before** planning. Skip only for throwaway work.
4. `/speckit.plan` — produce the technical plan and design artifacts (the *how*, tech stack, architecture).
5. `/speckit.tasks` — generate the dependency-ordered `tasks.md`.
6. `/speckit.analyze` — cross-check spec ↔ plan ↔ tasks for gaps and inconsistencies (non-destructive).
7. `/speckit.implement` — execute the tasks to build the feature.

Optional: `/speckit.checklist` (custom quality gates), `/speckit.converge` (reconcile a drifted codebase against the spec), `/speckit.taskstoissues` (export tasks to GitHub issues).

**Rules of engagement**
- Artifacts live under `specs/`, principles under `.specify/memory/constitution.md`. Treat them as the contract — update the spec when scope changes, then re-plan; never let code silently diverge from the spec.
- Each phase is a checkpoint: confirm the artifact looks right before advancing. Specs describe behavior and outcomes, not implementation; plans hold the technical choices.
- If the exact command names differ in this project, the installed ones are the source of truth — list them with `ls .claude/skills` (they are prefixed `speckit`).
- This workflow augments, and never overrides, the rest of this file or other project rules. When guidance conflicts, the project's own rules win.

To re-run setup, update Spec Kit to the latest version, or check status, invoke the **spec-kit** skill.
<!-- SPEC-KIT:END -->
