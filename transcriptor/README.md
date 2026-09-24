# 🎙️ Transcriptor de Reuniones (local, CPU)

Herramienta de línea de comandos para **transcribir grabaciones de reuniones** e
**identificar a los hablantes** (diarización). Funciona **100 % en local sobre CPU**
(sin GPU): el audio nunca sale de tu equipo.

- Acepta **m4a, mp3, wav, flac, ogg, opus, m4b, mp4** y más (los convierte con ffmpeg).
- Transcribe en **español** con Whisper (`large-v3-turbo` por defecto, vía faster-whisper).
- Etiqueta **quién habla y cuándo** con pyannote (`community-1`, modo
  **exclusive**: un hablante por instante, mejor alineado con Whisper).
- Genera **`.txt` legible**, **`.srt`** (subtítulos) y **`.json`** (datos estructurados).
- Pensada para audios **largos** y para ejecutarse a mano o desde Claude Code.

---

## 1. Requisitos

- **Windows** con **Python 3.11** (importante: versiones muy nuevas como 3.14 todavía no tienen paquetes compatibles de PyTorch/pyannote).
- **ffmpeg** instalado, **solo si lo usas a mano** con m4a/mp3/mp4… Si lo usas desde el
  [Grabador de Reuniones](https://github.com/mcjeikk/meeting-recorder), no hace falta: el
  Grabador le entrega el audio ya convertido.
- Una **cuenta de Hugging Face** con un token gratuito (solo para identificar hablantes).

> **¿Lo instalas para el Grabador de Reuniones?** Clónalo **en la misma carpeta que
> contiene `meeting-recorder`**, para que queden lado a lado; el Grabador lo encuentra
> solo:
>
> ```
> Proyectos\
> ├─ meeting-recorder\
> └─ meeting-transcriber\
> ```

---

## 2. Instalación (una sola vez)

Necesitas **[git](https://git-scm.com/download/win)** y **Python 3.11** (no uses 3.12+;
PyTorch/pyannote aún no traen paquetes para versiones muy nuevas). Abre **PowerShell** y ejecuta:

```powershell
# 1) Clonar el repositorio
git clone https://github.com/mcjeikk/meeting-transcriber.git
cd meeting-transcriber

# 2) Crear y activar un entorno virtual CON PYTHON 3.11
#    (usa 'py -3.11'; el 'python' por defecto del sistema puede ser otra versión incompatible)
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3) Instalar ffmpeg (solo para uso manual con m4a/mp3/mp4; el Grabador no lo necesita)
winget install Gyan.FFmpeg
#   (cierra y vuelve a abrir PowerShell para que ffmpeg quede en el PATH)

# 4) Instalar PyTorch en versión CPU (IMPORTANTE: antes que el resto de dependencias)
python -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu

# 5) Instalar el resto de dependencias
python -m pip install -r requirements.txt

# 6) (Opcional) Comprobar la instalación
python -m unittest discover -s tests
```

> Si prefieres reproducir **exactamente** el entorno validado, en el paso 5 usa
> `requirements.lock.txt` en lugar de `requirements.txt` (sigue haciendo falta el paso 4).

### Token de Hugging Face (para identificar hablantes)

La transcripción funciona sin token, pero **para diarizar (saber quién habla)** necesitas uno:

1. Crea un token en <https://huggingface.co/settings/tokens> (permiso de lectura).
2. **Acepta las condiciones** del modelo (es gratis, solo hay que aceptar):
   <https://huggingface.co/pyannote/speaker-diarization-community-1>
3. Copia el archivo `.env.example` como **`.env`** y pega tu token:

   ```
   HUGGINGFACE_TOKEN=hf_tu_token_real_aqui
   ```

> La **primera ejecución descarga los modelos** (~1.5 GB del modelo turbo + pyannote).
> Después la herramienta funciona **sin conexión a internet**.

---

## 3. Uso

```powershell
# Transcribir un archivo (español + hablantes, por defecto)
python transcribe.py "C:\ruta\reunion.m4a"

# Varios archivos en una sola ejecución (los modelos se cargan una vez)
python transcribe.py "reunion1.m4a" "reunion2.mp3" "reunion3.wav"

# Procesar TODOS los audios de una carpeta
python transcribe.py "C:\ruta\carpeta_audios" --batch

# Indicar el número de hablantes (mejora la precisión de la diarización)
python transcribe.py reunion.mp3 --speakers 4

# Poner nombres reales a los hablantes (en orden de aparición)
python transcribe.py reunion.m4a --names "Ana,Carlos,Sofía"

# Máxima precisión (más lento)
python transcribe.py reunion.m4a --model large-v3

# Más rápido / borrador
python transcribe.py reunion.m4a --model medium

# Solo transcripción, sin identificar hablantes
python transcribe.py reunion.m4a --no-diarize
```

**Atajo:** también puedes **arrastrar un archivo de audio sobre `transcribir.bat`**, o ejecutar
`transcribir.bat "reunion.m4a"`.

### Desde Claude Code

Basta con pedir, por ejemplo: *"transcribe `input\reunion.m4a`"*, y se ejecutará
`python transcribe.py "input\reunion.m4a"`.

---

## 4. Resultados

Por cada audio se crea una carpeta en `output\<nombre_del_audio>\` con:

| Archivo | Contenido |
|---|---|
| `transcripcion.txt`  | Texto legible con marcas de tiempo y hablante. |
| `transcripcion.srt`  | Subtítulos (para reproductores de vídeo). |
| `transcripcion.json` | Datos estructurados (bloques, segmentos, hablantes) para uso posterior. |

Ejemplo de `transcripcion.txt`:

```
# Transcripción: reunion.m4a
# Duración: 00:42:15   Idioma: es
# Hablantes: Hablante 1, Hablante 2, Hablante 3

[00:00:03 -> 00:00:11] Hablante 1: Buenos días a todos, comencemos con la reunión...
[00:00:12 -> 00:00:20] Hablante 2: Gracias. El primer punto del día es...
```

---

## 5. Configuración por defecto

Edita **`config.yaml`** para cambiar los valores por defecto (modelo, idioma, formatos,
número de hablantes, nombres, etc.) sin tener que escribir argumentos cada vez.

### GPU automática (`device: auto`)

La transcripción detecta la GPU **en cada ejecución**: si hay una NVIDIA con CUDA
utilizable, la usa (con `float16`); si no, corre en CPU (`int8`) como siempre. No hay
que tocar nada cuando el equipo gane una GPU. Se puede forzar con `--device cpu|cuda`.

> Nota para ese futuro: la **diarización** (pyannote/torch) usará la GPU solo cuando
> torch esté instalado con CUDA. Hoy está la versión CPU; para activarla:
> `pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu126`
> (el código ya está preparado: detecta `torch.cuda.is_available()` solo).

---

## 6. Rendimiento esperado (en CPU) y audios largos

El tiempo depende mucho de tu CPU. **Medición real en un portátil sin GPU dedicada**
(septiembre de 2026, 22 reuniones reales, modelo `large-v3-turbo` **con hablantes**):
procesar el audio toma aproximadamente **1.1× su duración** usando casi todos los núcleos,
y ~1.45× si se limitan para dejar el equipo usable. Más ~12 s de carga de modelos al
arrancar (una vez por ejecución, no por archivo).

| Duración del audio | Tiempo aprox. en ese portátil |
|---|---|
| 30 min | ~35 min |
| 1 hora | ~1 h 5 min |
| 3 horas | ~3 h 15 min |

En un equipo con CPU más potente (más núcleos rápidos) será bastante más rápido. El paso más lento
es la **diarización** (extracción de *embeddings* de los hablantes). Dividir en bloques NO acelera
esto (es el mismo volumen de audio); solo ayudaría a la memoria.

### Reuniones largas: procesamiento nocturno / desatendido (recomendado)

1. **Cierra otras aplicaciones** para liberar RAM (la diarización de audios largos usa varios GB).
2. Deja los audios en la carpeta `input\` (o pasa la ruta de un archivo).
3. Ejecuta **`transcribir_lote.bat`** (doble clic procesa todo lo que haya en `input\`). Deja el
   equipo encendido; puedes minimizar la ventana y volver más tarde.
4. El progreso se guarda en `output\log_<fecha>.txt` y los resultados en `output\<nombre>\`.

### Si necesitas el texto más rápido y los hablantes no son urgentes

- `--no-diarize` → aproximadamente **la mitad** del tiempo (solo transcripción).
- Modelo más ligero: `--model medium` o `--model small` (algo menos de precisión).
- `--beam-size 1` → un poco más rápido.

---

## 7. Solución de problemas

- **`No se encontró ffmpeg`** → instálalo (`winget install Gyan.FFmpeg`) y reabre la terminal.
- **No identifica hablantes** → falta el token o aceptar la licencia del modelo. Revisa el paso del
  `.env` y que aceptaste las condiciones en la web de Hugging Face.
- **`No se pudo activar el entorno (Activate.ps1)`** → ejecuta una vez en PowerShell:
  `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
- **Descarga del modelo turbo falla** → la herramienta reintenta con el repositorio
  `deepdml/faster-whisper-large-v3-turbo-ct2`. Si persiste, usa `--model medium`.
- **Va muy lento** → reduce el modelo (`--model medium`/`small`), `--beam-size 1`, o desactiva la
  diarización con `--no-diarize`.

### Plan B: WhisperX (un solo comando)

Si la instalación de pyannote diera problemas, existe una alternativa que empaqueta todo:

```powershell
pip install whisperx
whisperx "reunion.m4a" --compute_type int8 --device cpu --language es --diarize --hf_token TU_TOKEN
```

---

## 8. Notas

- **Identificación de hablantes:** la diarización agrupa voces y las nombra como
  *Hablante 1, Hablante 2…* (sabe *quién habla cuándo*, no el nombre real). Puedes asignar nombres
  con `--names` o en `config.yaml`. Reconocer personas por su voz automáticamente sería una mejora
  futura (requiere registrar huellas de voz).
- **Privacidad:** todo el procesamiento es local; el audio no se sube a ningún servicio.

---

## 9. Estructura del proyecto

```
Transcriptor/
├─ transcribe.py        # CLI principal
├─ pipeline/
│  ├─ audio.py          # conversión con ffmpeg -> WAV 16 kHz
│  ├─ asr.py            # transcripción (faster-whisper)
│  ├─ diarize.py        # diarización (pyannote community-1)
│  ├─ merge.py          # fusión texto <-> hablante por solape temporal
│  └─ output.py         # escritura .txt / .srt / .json
├─ tests/               # pruebas (python -m unittest discover -s tests)
├─ config.yaml          # valores por defecto
├─ requirements.txt
├─ .env.example         # plantilla del token de Hugging Face
├─ transcribir.bat      # atajo para Windows (arrastrar y soltar)
├─ input/               # (opcional) deja aquí tus audios
└─ output/              # resultados generados
```

---

## 10. Licencia

[MIT](LICENSE) © 2026 mcjeikk — libre para usar, copiar, modificar y distribuir,
conservando el aviso de copyright. Los modelos de terceros (Whisper, pyannote) tienen
sus propias licencias y condiciones de uso.
