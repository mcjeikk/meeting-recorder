# Plan para cambiar la interfaz del grabador

**Spec Kit 032 · Entregas verificadas · 25 de noviembre de 2026**
[Comportamiento y criterios de aceptación](./spec.md)

Las pantallas están implementadas en QML. Python gestiona la grabación, la transcripción y la integración con el escritorio. Las pruebas de ambas entregas están registradas en la [lista de tareas](./tasks.md).

## Primera entrega · Grabar una reunión de principio a fin

1. **Corregir Reanudar.** Reproducir con una fuente de prueba el fallo detectado en la auditoría. Coordinar el reloj y la apertura de video, audio y micrófono. Si falla un dispositivo, cerrar los recursos abiertos en ese intento y conservar los tramos previos. Mostrar Reanudar hasta que el motor confirme el éxito.
2. **Conectar la pantalla con el grabador.** Extraer de `MainWindow` las acciones de grabación y el estado que comparten botones, cronómetro y atajos. Reutilizar `Recorder`, la enumeración de fuentes y sus identificadores. Las operaciones lentas de los dispositivos deben permitir que la ventana siga respondiendo.
3. **Construir la vista Grabar en QML.** Colocar fuente, vista previa, micrófono y audio del sistema en la vista inicial. Reservar una franja fija para Grabar/Detener, Pausar/Reanudar y el tiempo. Mantener accesible «Transcribir al terminar». Reutilizar la captura nativa y su política de vista previa.
4. **Corregir la instalación y probar la entrega.** En Windows, `pyproject.toml` omite `psutil`, `opencv-python` y `windows-capture` que sí figuran en `requirements.txt`. Alinear las dependencias por plataforma y probar ambas instalaciones en entornos limpios. Incluir QML/Qt Quick y sus recursos en el paquete macOS, que hoy los excluye. Verificar en Windows y en el paquete instalado en Mac que se puede elegir una ventana, grabar, pausar, reanudar y reproducir el MP4 con las pistas habilitadas. Probar también cierre de la fuente, reintento, guardado de lo grabado, tamaño de ventana, teclado, atajos y exclusión de captura.

## Segunda entrega · Transcripciones y ajustes

5. Reunir importación, cola, progreso, reintento y apertura de resultados en Transcripciones. Corregir los dos botones que en Mac llaman a la función de Windows `os.startfile`. Usar Qt para abrir la carpeta y el registro de cada trabajo. Llevar calidad, consumo de CPU, idioma, hablantes, carpeta y audio avanzado a Ajustes.
6. Probar una transcripción de un archivo de muestra y el acceso a su resultado. Ejecutar las suites de la app y del motor, además de los casos de interfaz y guardado de la primera entrega.

## Comprobación de la constitución

La grabación tiene prioridad sobre la cola y la vista previa. Los medios se procesan localmente y el motor de transcripción conserva su proceso propio. La migración usa la ventana nativa para seguir gestionando bandeja, permisos y exclusión de captura.

## Cómo se trabajará

La especificación 031 ya resolvió el selector de ventanas. Todo el trabajo pendiente de la revisión se seguirá en esta especificación 032. Para cada tarea se anotará qué debe poder hacer el usuario, se reproducirá el fallo o el recorrido, se hará el cambio y se comprobará el resultado. La primera entrega se demostrará con un MP4 reproducible. La segunda se demostrará transcribiendo un archivo y abriendo su resultado. La lista de tareas distinguirá las pruebas ejecutadas de las pendientes en cada plataforma.
