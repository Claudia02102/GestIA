# GestIA — Sprint 4

Aplicación de escritorio local que muestra la webcam, detecta **un rostro** con MediaPipe
Tasks Face Landmarker, dibuja sus puntos y gestiona pérdida y recuperación (Sprint 1, Épica E1).

El Sprint 2 (Épica E2, «Calibración y perfiles») añade:

| Historia | Qué incluye |
|---|---|
| HU-06 Asistente de calibración | Asistente a pantalla completa que avanza solo con gestos: reposo, rango de cabeza (izquierda, derecha, arriba, abajo), gestos activos y verificación de las cuatro esquinas con un puntero virtual. Pide repetir un paso mal hecho. |
| HU-07 Selección de gestos | Activar o desactivar cada gesto; los desactivados no se reconocen ni aparecen en el mapeo. Debe quedar al menos un gesto de selección. |
| HU-08 Sensibilidad | Sensibilidad (1–10) y tiempo de sostenimiento por gesto, aplicados en vivo sin reiniciar. |
| HU-09 Guardado de perfil | La calibración y los ajustes se guardan en JSON local y se cargan al reabrir. |
| HU-10 Recalibración rápida | Gesto «Levantar las cejas» (o botón **Recentrar**): toma la postura actual como nuevo centro sin cambiar el resto del perfil. |
| HU-11 Múltiples perfiles | Crear, cambiar y eliminar (con confirmación) perfiles en el mismo equipo. |

El Sprint 3 (Épica E3, «Control del puntero») mueve el **cursor real** del sistema:

| Historia | Qué incluye |
|---|---|
| HU-12 Cursor con la cabeza | La posición calibrada de la cabeza se lleva a la pantalla principal, llega a todos los bordes y una zona muerta evita que se mueva con la cabeza quieta. |
| HU-13 Clic izquierdo | «Abrir la boca» hace un solo clic en la posición del cursor. |
| HU-14 Clic derecho y doble clic | «Sonreír» → clic derecho; «Guiño izquierdo» → doble clic (gestos distintos). |
| HU-15 Clic por permanencia | Opcional: clic al mantener el cursor quieto el tiempo y radio configurados. |
| HU-16 Arrastrar y soltar | «Guiño derecho» presiona; el mismo gesto (o el de clic) suelta. Si se pierde el rostro, se cancela (Esc y vuelta al origen). |
| HU-17 Desplazamiento | «Fruncir los labios» activa el modo: alejar la cabeza del centro desplaza vertical u horizontalmente; repetir el gesto vuelve al control normal. |
| HU-18 Velocidad y suavizado | Velocidad (×0,5 a ×3), suavizado (filtro One Euro, 0–10) y zona muerta por perfil. |

El Sprint 4 (Épica E4, «Escritura en pantalla») añade un **teclado virtual** que escribe en
cualquier aplicación:

| Historia | Qué incluye |
|---|---|
| HU-19 Teclado virtual | Ventana flotante siempre encima que no toma el foco; se pulsa con el cursor de la cabeza y el gesto de clic (o por permanencia). Incluye ñ, tildes y signos. |
| HU-20 Predicción de palabras | Tres sugerencias en español según las primeras letras; aprende las palabras que se escriben (una nueva se sugiere desde la segunda vez). |
| HU-21 Teclas especiales y atajos | Intro, Borrar, Supr, Tab, Esc, flechas, Inicio, Fin, Mayús, Bloq Mayús y Copiar, Pegar, Cortar, Deshacer, Seleccionar todo. |
| HU-22 Frases frecuentes | Lista editable por perfil; una selección escribe la frase completa. |
| HU-23 Teclado ajustable | Tamaño de tecla y distribución (QWERTY o alfabética), guardados en el perfil; el teclado nunca se sale de la pantalla. |

Además, «Cerrar ambos ojos», el botón **Pausar control** o **Ctrl+Alt+P** (desde cualquier
aplicación) pausan y reanudan el control. Es un adelanto de HU-29 (Épica E6) para poder
detener el cursor con seguridad. La utilidad de accesibilidad debe evaluarse con usuarios; no
es un resultado demostrado.

## Requisitos

- Windows 10 u 11 de 64 bits (x86-64).
- CPython 3.11 o 3.12 de 64 bits (por ejemplo, desde python.org).
- Webcam integrada o USB con acceso permitido en *Configuración → Privacidad y seguridad →
  Cámara* (incluida la opción «Permitir que las aplicaciones de escritorio accedan a la cámara»).

Las versiones están fijadas en `pyproject.toml`. MediaPipe 0.10.21 dispone de wheels CPython
3.11 y 3.12 para Windows x86-64. El proyecto declara `opencv-python`; en Windows, MediaPipe
instala además `opencv-contrib-python` como dependencia propia.

## Instalación

En PowerShell, desde la raíz del proyecto:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
Copy-Item config.example.json config.json
python tools/download_model.py
```

Si PowerShell bloquea `Activate.ps1`, ejecute los comandos sin activar el entorno usando
`.venv\Scripts\python.exe` en lugar de `python`.

El último comando realiza una descarga explícita del bundle oficial FaceLandmarker desde
Google. El modelo se guarda en `models/face_landmarker.task` y no se versiona. Después de
instalar dependencias y descargarlo, la aplicación funciona sin Internet.

## Ejecución

Desde la raíz, con el entorno activado:

```powershell
python -m gestia
# Opcional:
gestia --config config.json
gestia --camera 1
```

Seleccione una cámara y pulse **Iniciar**. Sin rostro debe permanecer en «Buscando rostro».
Tras el periodo estable muestra «Rostro detectado». Al salir del encuadre retira los puntos y
muestra pérdida; al volver recupera el seguimiento sin reiniciar. **Detener** libera la cámara
y permite iniciar de nuevo.

### Flujo del Sprint 2

1. La primera vez se crea el perfil «Perfil 1». Al detectarse el rostro, si el perfil no está
   calibrado, el **asistente de calibración** se abre solo a pantalla completa.
2. Cada paso avanza al **mantener** la posición indicada (barra de progreso y pitido al
   completarlo). No hace falta teclado ni ratón; el botón *Cancelar* es para quien asiste.
   - Si el movimiento es insuficiente, va hacia el lado equivocado o no se sostiene, el paso
     se repite. Un gesto que no se logra en 3 intentos se omite y queda desactivado.
   - En la verificación final hay que llevar el puntero virtual a las cuatro esquinas. Si no
     se logra en 30 s, se repite solo el rango de cabeza.
3. En la pestaña **Gestos** puede activar/desactivar gestos, cambiar sensibilidad y tiempo de
   sostenimiento; la barra muestra en vivo la intensidad del gesto. **Mapeo** lista los gestos
   activos con su acción y **Eventos** registra los gestos reconocidos.
4. Con **Controlar el cursor del sistema** marcado (por defecto), el cursor sigue la cabeza
   en cuanto el perfil está calibrado. Para que quien asiste recupere el ratón: desmarque la
   casilla, pulse **Ctrl+Alt+P** o cierre los ojos ~1 s. La pestaña **Puntero** ajusta
   velocidad, suavizado, zona muerta, clic por permanencia y velocidad de desplazamiento.
5. Si cambia de postura, levante las cejas (≈1 s) o pulse **Recentrar** y quédese quieto: el
   centro se actualiza en ~1 s (límite 4,5 s).
6. **Mostrar teclado** abre el teclado virtual abajo de la pantalla. Haga clic primero en la
   aplicación donde quiere escribir; las teclas se pulsan con el gesto de clic y el texto va
   a esa aplicación. **Frases** cambia a las frases frecuentes. La pestaña **Teclado** ajusta
   distribución, tamaño, frases y permite olvidar las palabras aprendidas.
7. **Nuevo perfil**, el selector y **Eliminar perfil** gestionan varias personas usuarias.
   **Calibrar** repite el asistente completo para el perfil activo.

Gestos y acción asignada por defecto (la reasignación es la Épica E5):

| Gesto | Acción | Activo por defecto |
|---|---|---|
| Abrir la boca | Clic izquierdo | Sí |
| Sonreír | Clic derecho | Sí |
| Fruncir los labios | Modo desplazamiento | Sí |
| Cerrar ambos ojos (≥ 800 ms) | Pausar / reanudar | Sí |
| Levantar las cejas (≥ 1 s) | Recalibrar (recentrar) | Sí |
| Guiño izquierdo | Doble clic | No |
| Guiño derecho | Arrastrar y soltar | No |

Los perfiles creados en el Sprint 2 se cargan sin problema, pero «Fruncir los labios» aparece
*Sin calibrar*: pulse **Calibrar** una vez para incluirlo.

## Configuración y datos

`config.json` permite cambiar índice, resolución, FPS solicitados, periodo estable, antigüedad
máxima de resultados y los tres umbrales `[0,1]` de Face Landmarker. La sección `calibration`
ajusta los tiempos del asistente (sostenimiento, tiempo límite por paso, verificación), el
desplazamiento mínimo de cabeza, la tolerancia de quietud, el alcance (`reach`: fracción del
rango cómodo que ya lleva el puntero al borde) y el recentrado. `profiles.directory` indica
dónde se guardan los perfiles (`data/profiles` por defecto).

Cada perfil es un JSON en `data/profiles/<id>.json` con los gestos activos, la sensibilidad,
el mapeo y la calibración. La calibración son solo **razones geométricas escalares** (por
ejemplo, la apertura de la boca en reposo y en el gesto pleno), no imágenes ni landmarks.
`data/profiles/index.json` recuerda el último perfil usado.

Las métricas y datos técnicos del entorno (SO, arquitectura, CPU lógica, RAM, Python y sesión
gráfica) se guardan como JSONL en `data/metrics.jsonl`. No se guardan fotografías, video,
landmarks ni información de identidad.

## Verificación

```powershell
ruff check .
pytest
```

La [matriz manual](docs/MATRIZ_PRUEBAS_WEBCAM.md) explica cómo probar luz frontal, luz tenue,
contraluz, lentes transparentes, pérdida, desconexión y reinicio. Debe llenarse con resultados
reales: las pruebas simuladas no demuestran FPS ni robustez física. Consulte también el
[informe del Sprint 1](docs/INFORME_SPRINT_1.md), el
[informe del Sprint 2](docs/INFORME_SPRINT_2.md) y la
[matriz de aceptación del Sprint 2](docs/MATRIZ_PRUEBAS_SPRINT_2.md), el
[informe del Sprint 3](docs/INFORME_SPRINT_3.md), la
[matriz de aceptación del Sprint 3](docs/MATRIZ_PRUEBAS_SPRINT_3.md), el
[informe del Sprint 4](docs/INFORME_SPRINT_4.md) y la
[matriz de aceptación del Sprint 4](docs/MATRIZ_PRUEBAS_SPRINT_4.md).

## Problemas frecuentes

- **Modelo ausente:** ejecute `python tools/download_model.py`.
- **Cámara no disponible:** pruebe otro índice (con una sola webcam suele ser 0), cierre otras
  apps que la usen (Teams, Zoom, la app Cámara) y revise los permisos de privacidad de Windows.
- **Desconexión:** detenga, reconecte y vuelva a iniciar. Se informa como ERROR, distinto de
  una pérdida facial.
- **Error `Invalid default 0.5`:** la aplicación fuerza `LC_NUMERIC=C` para evitar el conflicto entre Qt y protobuf en sistemas con coma decimal.
- **MediaPipe no instala:** confirme Python 3.11 o 3.12 de 64 bits (`py -0p` lista los
  instalados).
- **`CERTIFICATE_VERIFY_FAILED` al instalar:** algunos antivirus (por ejemplo Avast) inspeccionan
  HTTPS con su propio certificado. Exporte su certificado raíz, combínelo con los de `certifi` en
  un archivo PEM y configúrelo con `cert = <ruta>` en `.venv\pip.ini`, sin desactivar la
  verificación SSL.
- **El cursor no se mueve:** compruebe que el perfil esté *Calibrado*, que la casilla
  *Controlar el cursor del sistema* esté marcada y que el control no esté en pausa.
- **El cursor llega desplazado con escalado de Windows (125 %, 150 %):** se convierte a píxeles
  físicos; si aún ocurre, anote el escalado en la matriz. Solo se controla la pantalla principal.
- **Ventanas con permisos de administrador:** Windows no deja que una app normal haga clic en
  ellas (UIPI). Ejecute GestIA como administrador si necesita controlarlas.
- No instale además `opencv-python-headless`: comparte el módulo `cv2` con las otras variantes y puede sobrescribirlo.

## Arquitectura

- `capture.py`: cámara y buzón del frame más reciente.
- `vision.py`: adaptador MediaPipe sin dependencia de widgets.
- `tracking.py`: máquina de estados y validez temporal.
- `worker.py`: orquestación fuera del hilo principal.
- `ui.py`: visualización Qt Widgets.
- `persistence.py`: métricas técnicas locales.
- `features.py`: medidas faciales (giro, inclinación, ojos, boca, cejas, sonrisa) a partir de
  los landmarks.
- `gestures.py`: catálogo de gestos, acciones y motor de reconocimiento (umbral por
  sensibilidad, sostenimiento, histéresis).
- `calibration.py`: asistente de calibración, mapeo cabeza → puntero y recentrado (lógica pura).
- `profiles.py`: perfiles JSON y su almacén.
- `control.py`: control del puntero (filtro One Euro, zona muerta, clics, permanencia,
  arrastre, desplazamiento, pausa) y backend pynput.
- `keyboard.py`: teclado virtual (distribuciones, teclas especiales, atajos, frases) y backend
  pynput.
- `prediction.py`, `lexicon_es.py`: predicción de palabras con diccionario local y aprendizaje.
- `ui_calibration.py`, `ui_profile.py`, `ui_widgets.py`, `ui_keyboard.py`: asistente, panel de
  gestos, puntero virtual y ventana del teclado.

Flujo de datos: `capture` → `vision` (landmarks) → `tracking` (estado) → `features` →
`gestures` (en el hilo del worker) → `DisplayPacket` → `ui` (vista, asistente, recentrado,
perfil) → `control` (cursor del sistema).

Calibración, gestos, comandos y adaptador del SO se incorporarán cuando tengan comportamiento
real, sin crear módulos vacíos. No se crea ni publica ningún repositorio remoto en este sprint.

Fuentes: [guía oficial de Face Landmarker](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/python),
[modelo oficial](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/index)
y [MediaPipe 0.10.21](https://pypi.org/project/mediapipe/0.10.21/).
