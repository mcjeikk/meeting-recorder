# Quickstart: Validate Refresh Capture Devices

**Feature**: `001-refresh-devices`  
**Date**: 2026-07-27  

Guía de validación manual / smoke tras implementar. Detalle de contratos: [contracts/ui-refresh-devices.md](./contracts/ui-refresh-devices.md). Modelo: [data-model.md](./data-model.md).

## Prerequisites

- Windows con al menos un micrófono (idealmente dos: uno fijo + uno USB/Bluetooth enchufable).
- Venv del Recorder activo o usar el intérprete del proyecto.
- Proyecto hermano Transcriptor **no** requerido para esta feature.

```powershell
cd "C:\Users\jeissonsegura\OneDrive - Periferia IT Corp SAS\Documentos\Proyectos\Apps\Recorder"
.\.venv\Scripts\python.exe smoke_test.py
```

## Setup

1. Lanzar la app (entrypoint habitual del proyecto, p. ej. módulo principal / script de arranque).
2. Confirmar que aparecen secciones “¿Qué quieres grabar?” y “Micrófono”, cada una con su acción Actualizar (tras la feature).

## Scenarios

### Q1 — Mic aparece tras conectar (P1 / C-MIC-REFRESH)

1. Con la app abierta, anotar la lista de mics.
2. Conectar un micrófono nuevo.
3. Pulsar **Actualizar** en Micrófono (no el de fuentes).
4. **Esperado**: el mic nuevo aparece en &lt; 3 s; se puede seleccionar; el medidor reacciona al hablar (idle).

### Q2 — Conservar selección sin cambio de hardware (P2 / FR-003)

1. Elegir un micrófono que **no** sea el primero de la lista.
2. Pulsar Actualizar mics sin enchufar/desenchufar nada.
3. **Esperado**: el mismo mic sigue seleccionado (≥ 9/10 intentos en prueba repetida).

### Q3 — Mic desconectado (FR-007)

1. Seleccionar un mic extraíble; desconectarlo; Actualizar mics.
2. **Esperado**: deja de aparecer (o no queda como selección válida); hay fallback (“Sin micrófono” u otro) y mensaje breve de estado; la app no cierra.

### Q4 — Hot-swap durante grabación (FR-006 / SC-004)

1. Iniciar grabación corta.
2. Verificar: combo/fuente Actualizar de **video** deshabilitados; mic + Actualizar mics **habilitados**.
3. Actualizar mics; elegir otro mic (o conectar uno nuevo, refrescar, elegir).
4. **Esperado**: grabación no se detiene; al reproducir, el audio del mic nuevo está en la pista (o silencio si se eligió “Sin micrófono”).

### Q5 — Paridad fuentes (P3 / C-SRC-REFRESH)

1. En idle, abrir una ventana con título distintivo.
2. Pulsar Actualizar en fuentes; seleccionarla.
3. Volver a Actualizar sin cerrarla.
4. **Esperado**: sigue seleccionada; vista previa coherente.
5. Iniciar grabación: controles de fuente deshabilitados.

### Q6 — Headless smoke (sin dispositivos reales)

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
$env:PYTHONIOENCODING = "utf-8"
.\.venv\Scripts\python.exe smoke_test.py
```

**Esperado**: no crash. Si se añaden asserts headless sobre `MainWindow` sin `show()`, validar que existen handlers de refresh de mics/fuentes y que `_refresh_mics` no fuerza siempre índice 1 cuando hay selección previa (mock de lista).

## Done criteria for this feature

- [ ] Q1–Q5 pasan en máquina real  
- [ ] Q6 / smoke no regresa  
- [ ] Contratos C-MIC-REFRESH, C-SRC-REFRESH, C-RECORDING-GATES cumplidos  
- [ ] Sin hotplug implementado (fuera de MVP — no marcar como fallo)
