# 🎥 Grabador de Reuniones

Aplicación de escritorio para **grabar reuniones** (Teams, navegadores y cualquier app) capturando a la vez:

- 🖥️ **Video** de una **ventana** o de la **pantalla completa** (a tu elección)
- 🔊 **Audio del sistema** (lo que escuchas por los parlantes)
- 🎤 **Micrófono**

El resultado es un archivo **MP4** con **pistas de audio separadas** (sistema y micrófono) más una **pista mezclada** que se reproduce normal en cualquier reproductor. Y si activas la casilla **"Transcribir al terminar"** *(opcional)*, la app genera automáticamente la **transcripción con identificación de hablantes** usando el proyecto **Transcriptor** —un proyecto **independiente que instalas aparte** (100 % local; el audio nunca sale de tu equipo). Sin Transcriptor instalado, la grabación funciona igual: solo no se genera la transcripción.

> **Estado actual:** Windows con grabación + transcripción automática funcionando. macOS y Linux están planificados (ver `Roadmap`).

---

## ✅ Requisitos

- **Windows 10/11**
- **Python 3.10 o superior** ([descargar](https://www.python.org/downloads/))
- No necesitas instalar FFmpeg aparte: viene incluido vía `imageio-ffmpeg`.
- No necesitas "Stereo Mix" ni cables virtuales: el audio del sistema se captura con **WASAPI loopback**.

---

## 🚀 Instalación (paso a paso)

Necesitas **[git](https://git-scm.com/download/win)** y **[Python 3.10+](https://www.python.org/downloads/)**
instalados. Abre **PowerShell** y ejecuta:

```powershell
# 1) Clonar el repositorio
git clone https://github.com/mcjeikk/meeting-recorder.git
cd meeting-recorder

# 2) Crear un entorno virtual (aísla las dependencias).
#    Se recomienda Python 3.11. Si el lanzador "py" no existe, usa "python".
py -3.11 -m venv .venv        # alternativa:  python -m venv .venv

# 3) Activarlo
.\.venv\Scripts\Activate.ps1

# 4) Instalar las dependencias
pip install -r requirements.txt

# 5) (Opcional) Comprobar que el entorno quedó correcto
python smoke_test.py
```

> Si PowerShell bloquea la activación, ejecuta una vez:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

---

## ▶️ Abrir la app (doble clic, sin terminal)

Una vez instalado (paso anterior), tienes varias formas de abrirla con **doble clic**:

- 🖱️ **Acceso directo en el Escritorio** y en el **menú Inicio**: *"Grabador de Reuniones"*
  (se abre sin ventana de consola). Si lo borras o mueves la carpeta, ejecuta
  **`Crear acceso directo.bat`** para recrearlo.
- 📄 **`Grabador.vbs`** dentro de la carpeta del proyecto: doble clic y listo.

O desde la terminal, si prefieres:
```powershell
python -m app.main
```

Se abre una ventana con **tema oscuro**. Sigue el orden de arriba hacia abajo:

1. **¿Qué quieres grabar?** → elige una **ventana** de la lista o una **pantalla**
   (si tienes varios monitores, cada uno aparece como «Pantalla N»).
   Verás una **vista previa** (miniatura) de lo que se grabará. Usa **🔄 Actualizar**
   para refrescar la lista de ventanas abiertas.
2. **Micrófono** → elige tu micrófono. El medidor muestra el nivel **en vivo,
   incluso antes de grabar** (para que verifiques el sonido al configurar).
   👉 **Puedes cambiar de micrófono o silenciarlo (botón 🎤/🔇) durante la grabación.**
   - **Indicador de reunión**: la app detecta si **Teams/Zoom/Meet u otra app está
     usando el micrófono** (igual que el ícono junto al reloj) y lo muestra.
   - Opción **experimental**: *"Auto-silenciar fuera de llamada (experimental)"*
     — silencia **tu pista de grabación** cuando Windows no ve ninguna app de
     reunión usando el mic; la reactiva al detectar llamada. Solo actúa al
     **entrar/salir** de llamada (un mute manual durante la llamada se respeta
     hasta el siguiente cambio). **No** sigue el mute interno de Teams (si
     Teams sigue capturando, Windows cree que hay llamada): para eso usa 🔇 o
     Ctrl+Shift+M.
3. **Audio del sistema** → déjalo **activado** para grabar lo que suena en la reunión.
4. **Carpeta de salida** → dónde se guardará el archivo.
5. Pulsa **● Grabar**. El botón cambia a **■ Detener** y aparece **⏸ Pausar**; verás
   un cronómetro y un punto rojo de grabación.
6. Al **Detener**, la app genera el MP4 final y te ofrece **Abrir carpeta**.

### ⌨️ Atajos y comodidades
- **Ctrl + Shift + R** → iniciar / detener (funciona aunque la app no esté enfocada).
- **Ctrl + Shift + P** → pausar / reanudar. *(El tiempo en pausa no cuenta en el video.)*
- **Ctrl + Shift + M** → silenciar / activar el micrófono. *(Muteado = se graba
  silencio en tu pista, sin perder la sincronía.)*
- **La ventana del recorder NO aparece en la grabación**: se excluye de la captura
  pero sigue visible y usable para ti (incluso con vista previa en vivo).
- **Ícono en la bandeja** para control rápido. La **X** cierra la app (si hay una
  grabación, la finaliza antes de salir). **Ctrl+C** en la consola también la cierra.
- **Sincronización automática**: el audio se alinea con el video aunque cada flujo
  arranque con una latencia distinta.

### 🎧 Eco al grabar con altavoces
Si escuchas la reunión por **altavoces**, tu micrófono captará ese sonido y se oirá
**eco**. Dos ayudas:
1. La forma más limpia es usar **audífonos** (elimina el eco de raíz).
2. Activa **"Reducir eco del micrófono"** (casilla en *Audio del sistema*): al
   terminar la grabación, la app usa el audio del sistema como referencia para
   **cancelar el eco** de tu pista de micrófono (filtro adaptativo; ~15 dB de
   reducción en pruebas). El procesado tarda unos segundos al finalizar.

### ⚠️ Bluetooth y audio del sistema
Si la **salida por defecto** de Windows es un auricular **Bluetooth**, en muchos
equipos el loopback WASAPI deja la pista **Sistema en silencio** (oyes la reunión
en el headset, pero Windows no deja capturar esa mezcla). La app avisa cuando
detecta esa ruta. Para grabar el audio de los demás participantes:
1. En Windows, cambia la salida a **Altavoces** (o un dispositivo con cable), o
2. Usa un cable virtual (p. ej. VB-Audio) si debes quedarte en Bluetooth.
El **micrófono** Bluetooth (Hands-Free) sí se puede grabar; el problema es solo
la captura de lo que *suena* por el auricular.

### 🎙️ Nota sobre el mute en reuniones (Teams/Zoom/Meet)
La app **no puede saber** si te silenciaste *dentro* de Teams: ese mute es interno
de la app de reunión y **no se refleja en ninguna señal de Windows** (lo verificamos:
ni el estado de la sesión de audio, ni el mute del dispositivo, ni el registro
cambian al mutearte en Teams; Teams sigue capturando el micrófono). Por eso, para no
grabar tu voz cuando estás en silencio, usa el **botón 🔇** o el atajo **Ctrl+Shift+M**.

---

## 📦 Qué se genera

Para cada grabación obtienes un **`.mp4`** con:

| Pista | Contenido |
|-------|-----------|
| 1 | 🔊 Audio del sistema (los demás participantes) |
| 2 | 🎤 Tu micrófono |
| 3 | 🎚️ Mezcla de ambos (para reproducir normal) |

Durante la captura se usan archivos temporales **MKV/WAV** (resistentes a cierres inesperados); al detener se combinan en el MP4 final.

---

## 📝 Transcripción automática (Fase 2)

Marca la casilla **"📝 Transcribir al terminar"** (sección 4) y, al detener cada
grabación, la app la transcribe sola con el proyecto **Transcriptor** (faster-whisper
+ pyannote, en local). Los resultados quedan junto a tus videos:

```
<carpeta de salida>\Transcripciones\<nombre_grabacion>\
├─ transcripcion.txt   # [HH:MM:SS] Hablante N: texto
├─ transcripcion.srt   # subtítulos
└─ transcripcion.json  # bloques por hablante con tiempos (para procesar después)
```

### Cómo se comporta (diseñado para que "simplemente funcione")

- **La grabación siempre manda**: la transcripción nunca arranca mientras grabas y,
  si empiezas a grabar a mitad de una, el proceso se **pausa por completo** (cero
  CPU, sin perder el avance) y se reanuda al detener. Además corre con prioridad
  baja y deja 2 núcleos libres.
- **Sobrevive al cierre de la app**: puedes cerrar el Grabador con una transcripción
  en curso; el proceso continúa solo y al reabrir la app se retoma el estado
  (la cola es persistente en `%LOCALAPPDATA%\MeetingRecorder\transcripts`).
- **Cola y reintentos**: varias grabaciones se transcriben en orden, de a una. Si la
  identificación de hablantes falla (memoria, token), se reintenta automáticamente
  sin diarización en vez de perder horas de trabajo.
- **GPU automática**: hoy corre en CPU (~2x la duración del audio en este equipo).
  El día que el equipo tenga GPU NVIDIA, la usará solo, sin tocar configuración.
- **Sin hablantes** en el resultado = falta el token de HuggingFace del Transcriptor
  (ver su README) o la diarización falló; la transcripción del texto no se pierde.

### Requisitos y configuración

> ⚠️ **La transcripción es opcional y depende de un proyecto aparte.** El **Transcriptor**
> (faster-whisper + pyannote) **no viene incluido en este repositorio**; se instala por
> separado desde **<https://github.com/mcjeikk/meeting-transcriber>**. Si no lo tienes, la
> grabación funciona igual: solo no se generará la transcripción.

- El proyecto **Transcriptor** debe estar instalado con su propio `.venv`, normalmente en
  una carpeta hermana (la ruta se autodetecta; se puede fijar con `transcriptor_dir` en
  `%APPDATA%\MeetingRecorder\config.json`, junto a `transcription_language` y
  `pause_transcription_while_recording`).
- Verificación rápida de toda la integración (sin pagar la diarización):

```powershell
python verify_transcription.py --quick          # última grabación
python verify_transcription.py "ruta.mp4" --force   # re-transcribir una concreta
```

---

## ⚙️ Cómo captura el video

- **Ventana específica** → usa **Windows.Graphics.Capture (WGC)**, que captura
  correctamente el contenido de ventanas aceleradas por GPU como **Teams, Chrome,
  Edge**, etc. (con el método antiguo `gdigrab` salían en negro).
- **Pantalla completa** → también **WGC** (captura del monitor por GPU), con
  respaldo automático a FFmpeg `gdigrab` si WGC falla. *¿Por qué?* gdigrab copia la
  pantalla por CPU y en monitores grandes no alcanza los 30 fps (medido: ~18 fps a
  3440×1440), lo que producía video "congelado a saltos" desincronizado del audio.

### ⚠️ Limitaciones (por diseño del sistema operativo)
- Ventanas con **DRM** (Netflix, etc.) o protegidas (`WDA_EXCLUDEFROMCAPTURE`) se
  graban en **negro** en cualquier método. No hay forma de evadirlo.
- Para capturar una ventana, **no puede estar minimizada** (restáurala antes de grabar).

---

## 🗺️ Roadmap

- **Fase 1 ✅:** MVP Windows — video + audio del sistema + micrófono → MP4.
- **Fase 2 ✅ (jun-2026):** Transcripción automática con el proyecto **Transcriptor**
  (subproceso + cola persistente; ver sección *Transcripción automática*).
- **Fase 3:** **macOS** (ScreenCaptureKit).
- **Fase 4:** **Linux** (PipeWire + xdg-desktop-portal).
- **Fase 5:** Empaquetado e instaladores firmados.

---

## 🧱 Estructura del proyecto

```
app/
├─ main.py              # Arranque de la app (PySide6)
├─ ui/                  # Interfaz (ventana principal)
├─ core/                # Orquestador, reloj maestro, configuración
├─ capture/             # Backends de captura por SO (video y audio)
├─ encode/              # Wrapper de FFmpeg (encode + mux)
└─ transcription/       # Integración con el Transcriptor
   ├─ integration.py    #   extracción de la pista "Mezcla" + comando del CLI
   ├─ jobs.py           #   cola persistente de trabajos (JSON atómicos)
   └─ worker.py         #   worker: gate de grabación, pausa, reintentos, re-adopción

verify_transcription.py  # prueba de humo de la integración (--quick)
verify_pipeline.py       # prueba end-to-end de la grabación
```

---

## 📄 Licencia

[MIT](LICENSE) © 2026 mcjeikk — libre para usar, copiar, modificar y distribuir,
conservando el aviso de copyright.
