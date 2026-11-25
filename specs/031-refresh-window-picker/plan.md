# Plan de implementación

**031-refresh-window-picker** · 24 de noviembre de 2026 · [Especificación](./spec.md)

## Diagnóstico y diseño

El barrido de Win32 encontró doce ventanas que devolvía el enumerador original. Dos correspondían a Teams. La lista de la captura contenía el calendario y se había poblado antes de abrir la reunión. El diálogo de Qt solo repetía la consulta al pulsar Actualizar. Además, el enumerador descartaba títulos repetidos y «Configuración», y el selector intentaba restaurar una ventana por su texto.

1. En Windows, actualizar el selector en `QComboBox.showPopup` antes de mostrarlo. Reutilizar la consulta del botón Actualizar. Bloquear la operación mientras el grabador está ocupado o grabando.
2. Conservar cada ventana visible con título por su `HWND`. Usar un orden estable para los títulos repetidos y numerarlos en la lista. Conservar el título original en `VideoSource` para la grabación y sus archivos.
3. Restaurar ventanas por identificador nativo y pantallas por índice. Una consulta fallida conserva la lista anterior. Un resultado válido donde desaparece la selección activa el respaldo a pantalla, informa al usuario e invalida cualquier miniatura anterior.
4. Verificar la apertura por teclado y ratón, las fuentes con nombres iguales, la selección que cambia de título y la prohibición de enumerar durante la grabación. Comparar el selector corregido con las ventanas reales de Teams usando solo sus identificadores y títulos.

## Constitución y alcance

La consulta ocurre en respuesta a una acción del usuario en reposo. La vista previa reutiliza el flujo puntual existente. Los identificadores y títulos se procesan localmente. La verificación de interfaz utiliza Qt sin audio real. En macOS se mantiene la actualización bajo demanda mediante el botón para evitar invocar ScreenCaptureKit al desplegar la lista.

## Componentes y verificación

Los cambios afectan al enumerador en `app/capture/windows_video.py`, a la identidad de `VideoSource` en `app/core/config.py` y al selector en `app/ui/main_window.py`. Las pruebas de regresión residen en `tests/test_window_sources.py`. La verificación incluye la suite del grabador y un barrido del escritorio Windows con el mismo selector que usa la aplicación.
