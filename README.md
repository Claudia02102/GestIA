# GestIA — Sprint 1

Aplicación de escritorio local que muestra la webcam, detecta **un rostro** con MediaPipe
Tasks Face Landmarker, dibuja sus puntos y gestiona pérdida y recuperación. Este sprint no
identifica personas, no controla la computadora y no incluye el catálogo de comandos de la
maqueta. Su utilidad de accesibilidad debe evaluarse con usuarios; no es un resultado demostrado.

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

## Configuración y datos

`config.json` permite cambiar índice, resolución, FPS solicitados, periodo estable, antigüedad
máxima de resultados y los tres umbrales `[0,1]` de Face Landmarker.

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
[informe](docs/INFORME_SPRINT_1.md).

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
- No instale además `opencv-python-headless`: comparte el módulo `cv2` con las otras variantes y puede sobrescribirlo.

## Arquitectura

- `capture.py`: cámara y buzón del frame más reciente.
- `vision.py`: adaptador MediaPipe sin dependencia de widgets.
- `tracking.py`: máquina de estados y validez temporal.
- `worker.py`: orquestación fuera del hilo principal.
- `ui.py`: visualización Qt Widgets.
- `persistence.py`: métricas técnicas locales.

Calibración, gestos, comandos y adaptador del SO se incorporarán cuando tengan comportamiento
real, sin crear módulos vacíos. No se crea ni publica ningún repositorio remoto en este sprint.

Fuentes: [guía oficial de Face Landmarker](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/python),
[modelo oficial](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/index)
y [MediaPipe 0.10.21](https://pypi.org/project/mediapipe/0.10.21/).
