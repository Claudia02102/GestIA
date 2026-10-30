# Informe breve — Sprint 1

## Implementado

- Selección por índice, inicio, detención y reinicio de cámara a 640×480 configurable.
- MediaPipe Tasks Face Landmarker para un rostro, puntos y recuadro derivado.
- Captura e inferencia fuera del hilo principal. Un buzón de capacidad uno reemplaza frames.
- Timestamps monotónicos y descarte de resultados atrasados o fuera de orden.
- Estados DETENIDO, BUSCANDO, SIGUIENDO, PERDIDO y ERROR con estabilización configurable.
- Métricas separadas de captura, resultados e inferencia; resumen JSONL técnico local.
- Umbrales de detección, presencia y seguimiento compatibles con Face Landmarker.
- Liberación de recursos y fallos diferenciados de ausencia de rostro.
- Pruebas simuladas. No se guarda ninguna imagen, video, landmark ni identidad.

## Validado sin hardware

Las pruebas automatizadas cubren transiciones, pérdida/recuperación lógica, estabilización,
resultados obsoletos, reemplazo de frames, configuración inválida y fallos simulados. Esto no
demuestra rendimiento o robustez con webcam real.

## Pendiente

- Completar la matriz en el equipo Windows 11 x86-64 de referencia.
- Confirmar ≥15 resultados/s y recuperación <2 s con el método documentado.
- Probar empaquetado en un sprint posterior y validar Windows por separado.
- Crear/publicar el repositorio remoto cuando se decida hacerlo.

Calibración, gestos, catálogo de comandos, tarjetas, mensajería, llamadas y control del SO
quedan fuera del Sprint 1.
