# UI contract: Transcribe file

## Placement

Grupo **4. Carpeta de salida** (transcripción ya vive ahí):

1. Checkbox **Transcribir al terminar** (existente)
2. Botón **Transcribir archivo…** (nuevo, primer nivel)
3. Hint muted: preset e idioma aplican también a archivos existentes; se puede arrastrar a la ventana
4. Combo velocidad/calidad + hint (existente)
5. Combo idioma (existente)

**Grabar** permanece en el bloque de botones de captura. No menú oculto como único acceso.

## File picker

- `getOpenFileNames` (multi-select)
- Filtro principal: audio/vídeo con extensiones de `SUPPORTED_MEDIA_EXTS`
- Filtro secundario: todos los archivos
- Directorio inicial: última carpeta de salida o home

## Drag and drop

- `MainWindow` acepta drops de URLs locales
- Al arrastrar tipos válidos: overlay “Suelta para transcribir”
- Carpetas / tipos inválidos: overlay o mensaje de rechazo; no enqueue
- Durante grabación: drop permitido (enqueue only)

## Feedback (non-modal)

| Situation | UI |
|-----------|-----|
| Enqueued 1 file | Banner de transcripción (cola) + status breve |
| Enqueued N files | Status: “N archivos en cola”; banner muestra el job actual/último emitido |
| already_done | Status: ya hay transcripción; botón Abrir si hay result_dir |
| already_active | Status: ya está en cola |
| unsupported / folder | Status: tipo no admitido |
| missing_tool | Mismo tooltip/disable que el resto de controles TX |
| missing_file | Status: el archivo no existe |

No `QMessageBox` de error para estos casos (FR-008).

## Queue controls

Cancel / Reintentar / Limpiar fallidos / Ver log / Abrir: sin cambios de contrato respecto a 003; aplican a jobs importados.
