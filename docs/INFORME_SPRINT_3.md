# Informe breve — Sprint 3 (Épica E3: Control del puntero)

## Implementado

- **`control.py`**: `PointerController`, lógica pura que recibe la posición normalizada de la
  cabeza (de la calibración del Sprint 2) y los eventos de gesto, y da órdenes a un backend de
  ratón. El backend real usa `pynput` (SendInput en Windows).
- **HU-12** Posición absoluta: reposo = centro de la pantalla principal; el rango cómodo
  calibrado cubre hasta los bordes. Conversión de píxeles lógicos de Qt a físicos (escalado
  de Windows). Zona muerta en píxeles para que la cabeza quieta no mueva el cursor.
- **HU-13 / HU-14** Clic izquierdo, derecho y doble clic, uno por gesto (el motor de gestos
  dispara una sola vez por gesto sostenido y se rearma al soltarlo).
- **HU-15** Clic por permanencia opcional: tiempo y radio configurables, un clic por parada,
  sin duplicar un clic hecho con gesto en el mismo punto.
- **HU-16** Arrastre: el gesto presiona el botón, el siguiente lo suelta. Si se pierde el
  rostro, se pausa o se desactiva el control, se cancela: Esc, vuelta al origen y soltar.
- **HU-17** Modo desplazamiento con un gesto nuevo, «Fruncir los labios» (misma medida que la
  sonrisa en sentido contrario; la calibración exige el sentido correcto). El cursor queda
  fijo; alejar la cabeza del centro desplaza en vertical y horizontal con velocidad
  proporcional. Repetir el gesto o hacer el de clic vuelve al control normal.
- **HU-18** Velocidad (×0,5–×3), suavizado con filtro One Euro (0–10) y zona muerta, por
  perfil y aplicados en vivo.
- Seguridad: casilla para desactivar el control, botón y atajo global **Ctrl+Alt+P** de pausa,
  pausa por gesto (adelanto de HU-29), sin control durante el asistente de calibración.
- Perfiles: nueva sección `pointer` (esquema 2). Los perfiles del Sprint 2 siguen cargando.

## Validado sin hardware

55 pruebas automatizadas (15 nuevas): bordes, zona muerta con temblor, velocidad, suavizado,
un clic por gesto en la posición del cursor, permanencia (tiempo, movimiento previo y cambio
de tiempo), arrastre, cancelación por pérdida de rostro, desplazamiento en ambos ejes y salida,
pausa, control desactivado, sentido de sonrisa/labios fruncidos y compatibilidad de perfiles.
Prueba de humo de la interfaz Qt con un ratón simulado: calibración completa con el gesto
nuevo, cursor en la esquina, clic, modo desplazamiento y pausa.

## Pendiente / riesgos

- Llenar la [matriz de aceptación](MATRIZ_PRUEBAS_SPRINT_3.md) en Windows con webcam real.
- Ajustar en hardware los valores por defecto de suavizado (`beta` del filtro), zona muerta y
  velocidad de desplazamiento.
- Solo se controla la pantalla principal. Varios monitores quedan para un sprint posterior.
- Windows impide controlar ventanas con privilegios de administrador desde una app normal.
- Reasignar gestos (E5) y la pausa completa con indicador sonoro (E6) siguen pendientes.
