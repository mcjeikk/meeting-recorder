# Tareas de la interfaz de grabación

## Primera entrega

- [x] T001 [FR-002] Añadir una regresión para reanudación fallida, reloj, etiqueta, reintento y guardado. Verificar las combinaciones de captura de video, micrófono y audio del sistema.
- [x] T002 [FR-002] Corregir la transición de pausa en `app/core/orchestrator.py` y `app/ui/main_window.py`. Completar T001 con el caso de fallo después de abrir un dispositivo.
- [x] T003 [FR-001, FR-003, FR-005] Extraer el controlador de la sesión que usarán QML y los atajos. Cubrir inicio, pausa, reanudación, guardado, error y recuperación.
- [x] T004 [FR-001, FR-003] Integrar la pantalla Grabar en QML con fuente, vista previa, niveles de audio y controles fijos. Verificar el selector con las pruebas de la especificación 031.
- [x] T005 [FR-001, FR-005] Probar el recorrido completo con una fuente controlada, el MP4, sus pistas, la vista de 480 × 720, el tamaño mínimo, el teclado y la exclusión de captura.
- [ ] T006 [FR-005, FR-006] Alinear las dependencias por plataforma de `pyproject.toml` y `requirements.txt` y comprobar que una prueba detecta futuras omisiones. En Windows instalar por separado con `pip install .` y `pip install -r requirements.txt` en entornos limpios. Incluir los módulos y recursos de QML en el paquete macOS. Comprobar que ambas instalaciones de Windows y la aplicación empaquetada en Mac permiten abrir el grabador y guardar un clip de prueba.

## Segunda entrega

- [x] T007 [FR-004, FR-005] Implementar las vistas Transcripciones y Ajustes, reutilizar la cola local y las preferencias existentes y sustituir las dos llamadas a `os.startfile` por apertura local multiplataforma.
- [ ] T008 [FR-001 a FR-006] Verificar importación, transcripción de muestra, apertura de la carpeta de resultados y del registro en Windows y Mac, recuperación del guardado y las suites de ambos entornos.

## Orden

T001 y T002 establecen el estado de grabación que necesita T003. T004 se apoya en el controlador. T005 y T006 validan la primera entrega. T007 y T008 completan las pantallas secundarias.

## Pruebas en Windows · 25 de noviembre de 2026

- El fallo se reprodujo al abrir el video, el audio del sistema y el micrófono. Tras la corrección, el reloj sigue en pausa y el botón muestra Reanudar. Se guardó el MP4 previo con las cuatro combinaciones de audio. Con ambas entradas se verificaron Sistema, Microfono y Mezcla.
- La prueba con una ventana verde en un proceso independiente selecciona su identificador nativo, comprueba la miniatura, pulsa Grabar y Pausar, entrega el atajo de reanudación a la ventana de prueba y pulsa Detener. FFmpeg verifica el color del video, el códec, la pista de audio y la duración. En Windows se usó un tono generado para la pista Sistema. Se comprobó también el valor de exclusión que devuelve Windows para la ventana del grabador.
- La prueba reveló que la espera inicial del codificador WGC podía acortar un clip de dos tramos. Se conservó el plazo de cada fotograma al recuperar el ritmo. La duración del MP4 se compara con el tiempo de grabación.
- Se probaron el tamaño inicial de 480 × 720, el mínimo de 360 × 320, el teclado y la franja fija. Las pruebas del selector cubren las ventanas con títulos iguales, los cambios de título y la llegada de una miniatura anterior.
- Se instalaron las dependencias con pip en dos entornos vacíos. El primero usó el paquete del proyecto y arrancó desde fuera del checkout. El segundo usó requirements.txt. Ambos guardaron clips de la fuente de prueba.
- Transcripciones importó nueve segundos de voz sintetizada en español. El motor escribió el texto y su registro. Los botones abrieron la carpeta del resultado y el archivo del registro a través del escritorio de Windows.
- Se verificó el reintento de guardado y la recuperación después de reiniciar el motor con tramos pendientes. La prueba comprueba que se recuperan solo los tramos terminados y sus pistas. El historial de las versiones anteriores sigue siendo legible.
