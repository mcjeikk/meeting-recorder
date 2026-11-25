# Interfaz de grabación

**Spec Kit 032 · Propuesta · 25 de noviembre de 2026**

## Escenarios de usuario

1. **Preparar y grabar una reunión (P1).** Al abrir el grabador, el usuario elige la ventana de Teams, comprueba el micrófono y el audio del sistema y pulsa Grabar. Durante la reunión puede ver el tiempo, pausar, reanudar y detener la grabación.
2. **Recuperarse de una reanudación fallida (P1).** Si la fuente deja de entregar imagen durante una pausa, el grabador explica qué ocurrió, conserva el tiempo grabado y permite reintentar o guardar lo que ya se grabó.
3. **Consultar transcripciones (P2).** Desde Transcripciones, el usuario puede importar un archivo, consultar la cola y abrir el resultado. La opción «Transcribir al terminar» sigue a mano cuando prepara una grabación.
4. **Instalar en otro equipo (P1).** En un entorno limpio, el usuario puede instalar el grabador en Windows siguiendo cualquiera de las dos vías existentes, abrir la pantalla principal y grabar. En macOS, la aplicación distribuida también incluye la pantalla nueva.

## Requisitos y aceptación

| ID | Requisito y comprobación |
| --- | --- |
| FR-001 | En una ventana de 480 × 720, la fuente, el micrófono, el audio del sistema y Grabar son accesibles en la primera vista. Grabar/Detener, Pausar/Reanudar cuando corresponda y el cronómetro quedan visibles al desplazarse por los ajustes. |
| FR-002 | Tras una reanudación fallida, el botón sigue ofreciendo Reanudar, el reloj continúa detenido y los segmentos anteriores se pueden guardar. Un reintento exitoso agrega un único tramo nuevo. |
| FR-003 | El selector conserva el comportamiento de la especificación 031, incluida la identidad de las ventanas de Teams. Una grabación iniciada desde la pantalla nueva usa exactamente la fuente seleccionada. |
| FR-004 | Transcripciones reúne importación, cola y resultados. Los botones para abrir la carpeta del resultado y el registro de la transcripción funcionan tanto en Windows como en macOS. La carpeta predeterminada, la calidad, el uso del PC, el idioma, el número de hablantes y las opciones avanzadas de audio se pueden consultar en Ajustes. |
| FR-005 | Los atajos y los botones reflejan el mismo estado. Al detener, la interfaz espera el resultado del guardado y permite recuperar una sesión pendiente. La captura y la transcripción son locales. |
| FR-006 | En Windows, las dos formas de instalación incluyen las dependencias de grabación necesarias. En un entorno limpio se puede abrir la nueva interfaz y grabar con cada una. El paquete de macOS permite el mismo recorrido. |

## Criterios de éxito

- Completar el recorrido elegir fuente, grabar, pausar, reanudar y guardar un MP4 válido con las pistas habilitadas.
- Comprobar la vista inicial y los controles persistentes con ratón y teclado. Probar también el tamaño mínimo de ventana admitido.
- Verificar pausa, error de reanudación, reintento y guardado con una fuente controlada. Ejecutar las suites del grabador y del transcriptor y comprobar la distribución para Windows y macOS.
- Abrir la carpeta y el registro de una transcripción de muestra mediante sus botones en Windows y en Mac.

## Decisiones de alcance

La grabación es la primera entrega. La reorganización de transcripciones y ajustes es la segunda. El panel oscuro y el botón verde de la especificación 019 sirven de referencia visual.
