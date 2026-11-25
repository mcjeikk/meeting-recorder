# Tareas de la interfaz de grabación

## Primera entrega

- [ ] T001 [FR-002] Añadir una regresión para reanudación fallida, reloj, etiqueta, reintento y guardado. Verificar las combinaciones de captura de video, micrófono y audio del sistema.
- [ ] T002 [FR-002] Corregir la transición de pausa en `app/core/orchestrator.py` y `app/ui/main_window.py`. Completar T001 con el caso de fallo después de abrir un dispositivo.
- [ ] T003 [FR-001, FR-003, FR-005] Extraer el controlador de la sesión que usarán QML y los atajos. Cubrir inicio, pausa, reanudación, guardado, error y recuperación.
- [ ] T004 [FR-001, FR-003] Integrar la pantalla Grabar en QML con fuente, vista previa, niveles de audio y controles fijos. Verificar el selector con las pruebas de la especificación 031.
- [ ] T005 [FR-001, FR-005] Probar el recorrido completo con una fuente controlada, el MP4, sus pistas, la vista de 480 × 720, el tamaño mínimo, el teclado y la exclusión de captura.
- [ ] T006 [FR-005, FR-006] Alinear las dependencias por plataforma de `pyproject.toml` y `requirements.txt` y comprobar que una prueba detecta futuras omisiones. En Windows instalar por separado con `pip install .` y `pip install -r requirements.txt` en entornos limpios. Incluir los módulos y recursos de QML en el paquete macOS. Comprobar que ambas instalaciones de Windows y la aplicación empaquetada en Mac permiten abrir el grabador y guardar un clip de prueba.

## Segunda entrega

- [ ] T007 [FR-004, FR-005] Implementar las vistas Transcripciones y Ajustes, reutilizar la cola local y las preferencias existentes y sustituir las dos llamadas a `os.startfile` por apertura local multiplataforma.
- [ ] T008 [FR-001 a FR-006] Verificar importación, transcripción de muestra, apertura de la carpeta de resultados y del registro en Windows y Mac, recuperación del guardado y las suites de ambos entornos.

## Orden

T001 y T002 establecen el estado de grabación que necesita T003. T004 se apoya en el controlador. T005 y T006 validan la primera entrega. T007 y T008 completan las pantallas secundarias.
