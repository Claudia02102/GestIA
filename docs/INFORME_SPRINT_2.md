# Informe breve — Sprint 2 (Épica E2: Calibración y perfiles)

## Implementado

- **Medidas faciales** (`features.py`): giro e inclinación aproximados de la cabeza (posición de
  la punta de la nariz entre mejillas y entre frente y mentón), apertura de cada ojo (EAR),
  apertura de boca, elevación de cejas y ancho de sonrisa. Son razones adimensionales,
  independientes de la distancia a la cámara.
- **Motor de gestos** (`gestures.py`): cada gesto se normaliza con su rango calibrado
  (reposo → gesto pleno, en cualquier sentido). Se dispara una vez al superar el umbral derivado
  de la sensibilidad durante el tiempo de sostenimiento; se rearma al bajar del 70 % del umbral.
  Parpadeo y guiños compiten en un grupo para que un guiño no cuente como parpadeo. Sin rostro
  fiable el motor se reinicia y no emite eventos.
- **HU-06** Asistente a pantalla completa, guiado solo por gestos: reposo, cuatro giros, gestos
  activos y verificación de las cuatro esquinas. Repite el paso ante movimiento insuficiente,
  sentido equivocado o pérdida del rostro; omite un gesto tras 3 intentos fallidos.
- **HU-07** Activar/desactivar gestos; los desactivados no se reconocen ni aparecen en el mapeo.
  Se impide desactivar el último gesto de selección con una advertencia.
- **HU-08** Sensibilidad 1–10 (umbral del 90 % al 20 % del gesto calibrado) y sostenimiento por
  gesto. Se envían al worker y se aplican en el siguiente fotograma, sin reiniciar.
- **HU-09** Perfil JSON con escritura atómica; se carga el último perfil usado al abrir.
- **HU-10** Recentrado por gesto (cejas) o botón: toma la mediana de ~0,8 s de quietud y desplaza
  el rango de cabeza; no modifica gestos ni sensibilidad. Límite de 4,5 s.
- **HU-11** Crear, cambiar y eliminar perfiles (con confirmación); cada uno guarda su calibración.
- Puntero virtual en miniatura para comprobar calibración y recentrado sin mover el cursor real.

## Validado sin hardware

40 pruebas automatizadas: medidas sobre una malla sintética, umbral/sensibilidad/sostenimiento/
histéresis, gestos desactivados y sin calibrar, guiño frente a parpadeo, recorrido completo del
asistente, repetición por sentido equivocado o movimiento insuficiente, omisión de gestos,
pérdida de rostro, verificación de esquinas fallida, recentrado (éxito < 5 s y fallo por
inestabilidad), persistencia, perfiles múltiples, perfiles dañados y configuración.
Además se ejecutó una prueba de humo de la interfaz Qt en modo *offscreen* con paquetes
simulados (asistente completo, eventos, recentrado, selección, sensibilidad y perfiles) y se
comprobó con una foto real que las medidas extraídas de MediaPipe tienen valores plausibles.

## Pendiente / riesgos

- Llenar la [matriz de aceptación](MATRIZ_PRUEBAS_SPRINT_2.md) con webcam y personas reales.
- Ajustar en hardware los márgenes por defecto (`min_head_delta`, `stable_tolerance`,
  desplazamientos mínimos de gesto en `calibration.py`). Son valores de partida.
- Confirmar con la cámara que «guiño izquierdo/derecho» corresponden al ojo esperado.
- El giro de cabeza se estima geométricamente; con giros amplios (> 35–40°) la malla pierde
  precisión. La Épica E3 podrá usar la matriz de transformación de MediaPipe si hace falta.
- Ejecución real de clics, pausa y movimiento del cursor: Épicas E3 y E6.
