# Matriz manual de pruebas con webcam

Estado: **pendiente de ejecución en hardware físico**. Las pruebas simuladas no validan
rendimiento, iluminación, lentes ni recuperación real.

## Equipo y método

Complete: fecha y versión; CPU/RAM; edición y compilación de Windows (`winver`);
marca/modelo de cámara; resolución observada; distancia rostro–cámara; uso de lentes.

Para cada fila inicie, espere 10 s, mueva e incline lentamente la cabeza, salga del encuadre
3 s y vuelva. Repita tres veces. Obtenga métricas de la interfaz y `data/metrics.jsonl`.
Mida recuperación desde el retorno visible del rostro hasta «Rostro detectado» e indique si
usó video de referencia o cronómetro.

| Caso | Luz | Lentes | Distancia | Resolución | Resultado | FPS resultados | Inferencia ms | Recuperación (3 intentos) | Notas |
|---|---|---|---:|---|---|---:|---:|---|---|
| 1 | Frontal normal | No | Pendiente | 640×480 | Pendiente | Pendiente | Pendiente | Pendiente | |
| 2 | Frontal normal | Transparentes | Pendiente | 640×480 | Pendiente | Pendiente | Pendiente | Pendiente | |
| 3 | Tenue | No | Pendiente | 640×480 | Pendiente | Pendiente | Pendiente | Pendiente | |
| 4 | Tenue | Transparentes | Pendiente | 640×480 | Pendiente | Pendiente | Pendiente | Pendiente | |
| 5 | Contraluz moderado | No | Pendiente | 640×480 | Pendiente | Pendiente | Pendiente | Pendiente | |
| 6 | Contraluz moderado | Transparentes | Pendiente | 640×480 | Pendiente | Pendiente | Pendiente | Pendiente | |
| 7 | Salida y retorno | Según caso 1 | Pendiente | 640×480 | Pendiente | Pendiente | Pendiente | Pendiente | PERDIDO → SIGUIENDO |
| 8 | Desconexión física | N/A | N/A | 640×480 | Pendiente | N/A | N/A | N/A | Debe mostrar ERROR |
| 9 | Detener/reiniciar ×5 | Frontal | No | Pendiente | 640×480 | Pendiente | Pendiente | Pendiente | |

No extrapolar a oscuridad, lentes opacos, otras cámaras, Windows ni toda la población.
Las metas de ≥15 resultados/s y recuperación <2 s siguen pendientes hasta llenar la matriz.
