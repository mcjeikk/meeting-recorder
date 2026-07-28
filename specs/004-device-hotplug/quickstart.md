# Quickstart: Device Hotplug Auto-Refresh

**Feature**: `004-device-hotplug`

## Automated

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_device_hotplug tests.test_list_microphones_refresh -q
```

## Manual (idle)

1. Abrir Meeting Recorder (no grabar).
2. Anotar micrófonos actuales.
3. Conectar auriculares BT o mic USB; esperar perfil Hands-Free si es BT.
4. **Sin** pulsar Actualizar: en ≤ ~5 s el nuevo mic debe aparecer.
5. Seleccionarlo → medidor reacciona.
6. Desconectar → lista actualiza; si era el seleccionado, cae a Sin micrófono u otro válido.

## Manual (recording Always Wins)

1. Iniciar grabación corta.
2. Conectar/desconectar un mic.
3. Esperado: grabación sigue; el mic nuevo puede no listarse aún.
4. Detener grabación → en idle la lista se actualiza (pending o nuevo evento).
5. Actualizar manual sigue funcionando.

## Regresión 001

- Botón Actualizar micrófonos en idle sigue haciendo deep refresh.
- Durante grabación, Actualizar no reinicia PortAudio.
