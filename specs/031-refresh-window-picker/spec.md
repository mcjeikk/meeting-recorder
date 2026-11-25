# Ventanas disponibles al elegir la fuente de captura

**Spec Kit 031** · 24 de noviembre de 2026 · Windows

## Escenarios de usuario y aceptación

### US1 · Elegir una reunión que acaba de abrirse (P1)

Con el grabador abierto y Teams en el calendario, el usuario entra en una reunión que se abre en otra ventana. Al desplegar «Fuente de captura», puede elegir la reunión con el ratón o el teclado. Si la reunión se cierra, desaparece la próxima vez que despliega la lista.

### US2 · Seguir grabando la ventana elegida (P1)

Si cambia el título de la ventana seleccionada o se abre otra con el mismo nombre, la selección sigue a la ventana original. Si dos ventanas comparten título, ambas se distinguen y cada una se puede elegir por separado. Una ventana de Configuración de Windows también se puede seleccionar.

### Casos de borde

- Si la ventana elegida se cierra, el selector muestra la pantalla de respaldo y actualiza la vista previa. El cambio de fuente debe ser visible.
- Si falla la consulta de ventanas, se conserva la última lista válida y se puede volver a intentar.
- Durante la preparación de una grabación, la grabación y su guardado, la selección de fuente queda bloqueada.
- En un navegador, la unidad de captura es la ventana. La lista incluye la ventana donde se muestra la pestaña activa.

## Requisitos

| ID | Comportamiento verificable |
| --- | --- |
| FR-001 | En Windows, cada apertura del selector en reposo presenta las ventanas abiertas en ese momento. El botón Actualizar sigue disponible. |
| FR-002 | Dos ventanas visibles con el mismo título tienen entradas distinguibles y la elección de cualquiera dirige su vista previa y su grabación a esa ventana. |
| FR-003 | Al refrescar, la selección sobrevive a un cambio de título u orden. Un monitor seleccionado conserva su selección. Si la ventana elegida desaparece, se comunica el cambio a la pantalla de respaldo. |
| FR-004 | Abrir el selector con la misma fuente seleccionada solo consulta la lista. Durante una grabación o transición se conserva la fuente y no se inicia otro barrido. |
| FR-005 | Una ventana visible con título de una aplicación como Configuración es elegible. Los componentes internos ocultos de Teams quedan fuera de la selección. |

## Criterios de éxito

1. Una ventana abierta después del grabador aparece al primer despliegue y se puede seleccionar sin pulsar otro botón.
2. Con dos ventanas de igual nombre, la vista previa y los ajustes de grabación apuntan a la elegida antes y después de renombrarla.
3. Un barrido local permite comparar las ventanas visibles de Teams con las fuentes ofrecidas. Las pruebas también cubren cierre, fallo de consulta, monitores y grabación en curso.

## Aclaración del barrido

La captura inicial mostraba el calendario. Al revisar el escritorio había dos ventanas visibles de Teams, el calendario y una reunión independiente, además de ventanas internas ocultas. La enumeración bajo demanda ya encontraba las dos. Esta diferencia delimita el problema de actualización del selector.
