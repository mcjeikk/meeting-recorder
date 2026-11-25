# Tareas y validación

- [x] T001 Comparar el escritorio con `list_windows`, revisar las especificaciones 001 y 018 y aclarar la diferencia entre el calendario, la reunión y las ventanas internas de Teams.
- [x] T002 [US1] Reproducir en `tests/test_window_sources.py` la apertura de una ventana posterior al inicio y la actualización por el selector.
- [x] T003 [US1] Actualizar antes de desplegar en Windows, respetar la grabación y conservar la lista si falla la consulta en `app/ui/main_window.py`.
- [x] T004 [US2] Cubrir títulos iguales, renombrado, cierre y la ventana de Configuración en `tests/test_window_sources.py`.
- [x] T005 [US2] Enumerar ventanas distintas en `app/capture/windows_video.py` y conservar su identidad en las etiquetas, la selección y la vista previa de `app/ui/main_window.py`.
- [x] T006 Ejecutar las pruebas y contrastar la lista corregida con las ventanas reales del escritorio.

## Revisión de coherencia antes de implementar

T002 y T003 cubren FR-001 y FR-004. T004 y T005 cubren FR-002, FR-003 y FR-005. T006 valida los tres criterios de éxito. El barrido y las pruebas del selector se pueden realizar sin iniciar una grabación de la reunión.

## Resultados en Windows · 24 de noviembre de 2026

- Las cinco pruebas iniciales reprodujeron los fallos antes del cambio. Las seis pruebas finales pasan, incluida la llegada tardía de una miniatura de la ventana anterior.
- El primer barrido encontró el calendario y la reunión como ventanas visibles independientes de Teams. En la captura compartida solo figuraba el calendario.
- En un segundo barrido, el selector corregido incluyó las ocho ventanas principales abiertas en ese momento. Teams mostraba el chat y sus ajustes de grabación conservaron su identificador. También se detectaron Chrome, Claude, ChatGPT, Outlook, Notepad++ y dos ventanas del Explorador.
- En la instancia abierta desde el lanzador habitual se comprobó después que la reunión independiente de Teams era la fuente seleccionada, con los controles Detener y Pausar disponibles.
- `run_all_tests.ps1` completó 316 pruebas del grabador y 10 del motor de transcripción.
