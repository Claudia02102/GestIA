# GestIA

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
| HU-13 Clic izquierdo | «Guiño izquierdo» hace un solo clic en la posición del cursor (P3-47). |
| HU-14 Clic derecho y doble clic | «Guiño derecho» → clic derecho; «Abrir la boca» → doble clic (gestos distintos). |
| HU-15 Clic por permanencia | Opcional: clic al mantener el cursor quieto el tiempo y radio configurados. |
| HU-16 Arrastrar y soltar | «Sonreír» presiona; el mismo gesto (o el de clic) suelta. Si se pierde el rostro, se cancela (Esc y vuelta al origen). |
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

Además, «Cerrar ambos ojos» (≥ 800 ms), el botón **Pausar control** o **Ctrl+Alt+P** (desde
cualquier aplicación) pausan y reanudan el control (P3-19). En pausa el cursor no se mueve y
ningún gesto actúa (ni clics, ni recentrar, ni el menú), salvo el de reanudar. Al pausar y
reanudar suena un aviso, y mientras dura la pausa un cartel amarillo arriba de la pantalla
indica cómo reanudar, aunque GestIA esté detrás de otra ventana. La utilidad de accesibilidad debe evaluarse con usuarios; no
es un resultado demostrado.

El Sprint 7 (Épica «Instalación, onboarding y aprendizaje») deja la app lista para personas
sin conocimientos técnicos:

| Historia | Qué incluye |
|---|---|
| P3-24 Instalación sencilla | Instalador `GestIA-Setup.exe` que se descarga desde la landing: no pide permisos de administrador ni instalar Python, incluye el modelo (funciona sin internet) y crea accesos directos. Se compila y publica solo en GitHub Releases al subir un tag. |
| P3-25 Inicio automático | Interruptor **Iniciar con Windows** en la cabecera (y casilla en el instalador, marcada por defecto). Al encender el equipo GestIA se abre sola, abre la cámara y, si el perfil está calibrado, queda minimizada y ya controlando el cursor. |
| P3-26 Tutorial y modo de práctica | Tras la primera calibración empieza solo un tutorial a pantalla completa: mover el puntero a cuatro objetivos y una lección por cada gesto activo con su acción real. **Practicar** abre un tablero libre. En ambos los gestos solo actúan en la pantalla del tutorial, nunca sobre el equipo. |

El Sprint 8 añade cuenta y licencia, y tres funciones de accesibilidad:

| Historia | Qué incluye |
|---|---|
| P3-62 Inicio de sesión y licencia | La versión instalada pide, la primera vez, el correo y la contraseña de la cuenta creada en la landing (el mismo proyecto de Supabase). Si la cuenta tiene la compra, el equipo queda activado (máximo 3). Luego **funciona sin internet**: solo vuelve a validar cada 30 días (y renueva sola en los últimos 7 días si hay conexión). Se guarda cifrado con DPAPI el token de sesión, nunca la contraseña. En desarrollo no se pide salvo con `GESTIA_REQUIRE_LICENSE=1`. |
| P3-64 Inclinar la cabeza → acciones rápidas | Inclinar la cabeza hacia un hombro (18° por defecto) y mantenerla medio segundo abre el menú; el mismo gesto lo cierra. Mientras la cabeza está inclinada el cursor se fija y los demás gestos esperan (evita guiños falsos). Se ajusta en **Atajos y auxilio**. |
| P3-65 YouTube | Botón **YouTube** en las acciones rápidas: abre youtube.com en el navegador predeterminado. |
| P3-66 Gesto de auxilio | Con un contacto configurado en **Atajos y auxilio**, mantener las cejas levantadas 3 s muestra una confirmación grande: abrir la boca o pulsar **Sí, enviar** abre WhatsApp Desktop en el chat del contacto y envía el mensaje de auxilio (sin WhatsApp Desktop, abre WhatsApp Web con el mensaje listo). Si no se confirma, se cancela sola a los 10 s. Funciona también en pausa. Soltar las cejas antes de 3 s recentra como siempre. No hace llamadas. |
| P3-27 Privacidad y uso sin conexión | La imagen de la cámara se procesa en memoria y nunca se guarda ni se envía. Solo la licencia se conecta a internet (correo, contraseña y un identificador cifrado del equipo); el modelo viene en el instalador. Las pruebas de `tests/test_privacidad.py` hacen fallar el CI si algún módulo guarda fotos o video, se conecta a internet o envía otros datos. Límites: la primera activación y la validación cada 30 días necesitan internet. |
| P3-67 Pipeline CI/CD por etapas | Un solo workflow en 4 etapas (lint y SAST, pruebas con cobertura, seguridad e instalador). El instalador solo se compila si todo lo anterior pasó. |

## Instalar GestIA (personas usuarias)

1. En la landing, pulse **Descargar para Windows**. Se descarga `GestIA-Setup.exe` desde
   [GitHub Releases](https://github.com/Claudia02102/GestIA/releases/latest).
2. Ábralo. Como el instalador aún no tiene firma digital, Windows puede mostrar «Windows
   protegió su PC»: pulse **Más información** y luego **Ejecutar de todas formas**.
3. Siga el asistente (Siguiente → Instalar). Deje marcada «Iniciar GestIA al encender el equipo»
   si la persona va a usar el equipo sin ayuda. No hace falta ser administrador.
4. Al terminar se abre GestIA: pulse **Iniciar**, siga la **calibración** y después el
   **tutorial**. Desde ese momento, cada vez que se encienda el equipo GestIA se abre sola.

Instalada, GestIA queda en `%LOCALAPPDATA%\Programs\GestIA` y los datos de cada persona
(configuración, perfiles, métricas y el registro `gestia.log`) en `%LOCALAPPDATA%\GestIA`.
Para desinstalar: *Configuración → Aplicaciones → GestIA → Desinstalar*. Se quitan el programa
y el inicio automático, pero se conservan los perfiles por si se vuelve a instalar.

**Inicio automático (P3-25).** El interruptor y el instalador usan el mismo valor `GestIA` de
`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`, así que siempre coinciden. Arranca
`GestIA.exe --autostart`, que pulsa **Iniciar** solo; si el perfil aún no está calibrado, la
ventana queda visible para que se abra la calibración. En desarrollo el interruptor también
funciona (arranca `pythonw -m gestia --autostart --data-dir <carpeta del proyecto>`).

**Tutorial y modo de práctica (P3-26).** Se construye con el mapeo y la calibración de la
persona: solo enseña gestos activos y calibrados, empezando por los clics y terminando por la
pausa. Las lecciones de clic piden llevar el puntero al círculo y hacer el gesto; si se hace otro
gesto, explica cuál fue y cuál toca. Si se pierde el rostro, el puntero se detiene y lo avisa.
Avanza solo; *Saltar lección*, *Reiniciar* y *Salir* son para quien asiste. Se ofrece una vez
por perfil (queda guardado en el perfil) y se repite con **Tutorial**. En **Practicar** cada
gesto muestra qué haría y se sale haciendo clic con un gesto sobre **Salir**.

## Requisitos

- Windows 10 u 11 de 64 bits (x86-64).
- CPython 3.11 o 3.12 de 64 bits (por ejemplo, desde python.org).
- Webcam integrada o USB con acceso permitido en *Configuración → Privacidad y seguridad →
  Cámara* (incluida la opción «Permitir que las aplicaciones de escritorio accedan a la cámara»).

Las versiones están fijadas en `pyproject.toml`. MediaPipe 0.10.21 dispone de wheels CPython
3.11 y 3.12 para Windows x86-64. El proyecto declara `opencv-python`; en Windows, MediaPipe
instala además `opencv-contrib-python` como dependencia propia.

## Instalación para desarrollo

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
   sostenimiento; la barra muestra en vivo la intensidad del gesto. En **Mapeo** cada gesto
   elige su acción en un desplegable: el cambio se aplica al instante y se guarda en el perfil.
   Si la acción ya la usa otro gesto, ambos intercambian sus acciones, y siempre debe quedar un
   gesto activo con clic izquierdo (o el clic por permanencia). **Eventos** registra los gestos
   reconocidos.
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
7. **Acciones rápidas** abre un menú a la derecha de la pantalla para navegar por Windows:
   cambiar de ventana (Alt+Tab), volver atrás (Alt+←), mostrar escritorio, cerrar ventana
   (pide confirmación) y abrir Explorador, navegador, Bloc de notas o Calculadora. No
   quita el foco: los atajos llegan a la aplicación activa. También se abre con un gesto si en
   **Mapeo** se le asigna «Acciones rápidas (menú)».
8. **Nuevo perfil**, el selector y **Eliminar perfil** gestionan varias personas usuarias.
   **Calibrar** repite el asistente completo para el perfil activo.
9. **Mapeo por aplicación:** en **Mapeo**, **Añadir aplicación** da un mapeo propio a una
   aplicación abierta (o a un ejecutable escrito, como `winword.exe`), que parte de una copia
   del general. Al hacer un gesto se usa el mapeo de la ventana activa; una aplicación sin mapeo
   propio, o GestIA, usa el general. En pausa, el gesto general de pausa siempre reanuda. Un
   arrastre o desplazamiento conserva hasta terminar el mapeo con el que empezó. Las aplicaciones
   de la Tienda de Windows pueden compartir el ejecutable `applicationframehost.exe` y, entonces,
   también el mapeo.
10. **Exportar** guarda el perfil activo en un archivo JSON e **Importar** lo añade en otro equipo
    como perfil nuevo y lo activa, sin sobrescribir ninguno (si el nombre existe, añade un número).
    Un archivo no válido muestra un error y no cambia nada. El archivo incluye calibración, frases
    y **palabras aprendidas**: compártalo solo con quien corresponda. Con otra cámara o postura,
    conviene **Recentrar** o **Calibrar** tras importar.
11. **Restaurar valores** (P3-18) devuelve el perfil activo a los valores iniciales tras pedir
    confirmación: gestos activos, sensibilidad y tiempo de cada gesto, mapeo general (y borra los
    mapeos por aplicación), ajustes del puntero y distribución y tamaño del teclado. Se conservan
    la calibración, las frases frecuentes y las palabras aprendidas. Si queda activo un gesto sin
    calibrar, avisa que hay que pulsar **Calibrar**.

Gestos y acción asignada por defecto (se puede cambiar en la pestaña **Mapeo**, HU P3-10):

| Gesto | Acción | Activo por defecto |
|---|---|---|
| Guiño izquierdo | Clic izquierdo | Sí |
| Guiño derecho | Clic derecho | Sí |
| Abrir la boca | Doble clic | Sí |
| Sonreír | Arrastrar y soltar | Sí |
| Fruncir los labios | Modo desplazamiento | Sí |
| Cerrar ambos ojos (≥ 800 ms) | Pausar / reanudar | Sí |
| Levantar las cejas (≥ 1 s) | Recalibrar (recentrar) | Sí |

Desde P3-47 los clics van en los guiños: abrir la boca baja el mentón, que mueve la
inclinación medida, y al cerrarla los labios se juntan como al fruncirlos. Además:

- Mientras se forma un gesto de la boca con clic, doble clic o arrastre asignado (desde la
  mitad de su umbral), el cursor queda **fijo** y la acción cae donde estaba. Con los guiños
  no se fija: girar la cabeza hace que un ojo parezca más cerrado y el cursor se trabaría.
- Durante 600 ms después de soltar un gesto de la boca, los otros gestos de la boca (sonreír,
  fruncir los labios) no cuentan, así que cerrar la boca ya no activa el desplazamiento.

**Gestos involuntarios (P3-22).** Un gesto solo cuenta si se sostiene el tiempo configurado
en **Gestos**. Un parpadeo natural no es un guiño ni pausa: en el grupo de los ojos gana el
gesto más marcado y la pausa exige 800 ms. Al **hablar**, la boca se abre y se cierra varias
veces seguidas: con 3 aperturas en 2 s, los gestos de la boca (abrir, sonreír, fruncir) esperan
hasta 1,2 s después de la última, así que conversar o reír hablando no hace doble clic ni
arrastra. La pestaña **Eventos** avisa cuando empieza y termina esa espera.

**Retroalimentación e indicador de estado (P3-44).** Abajo a la derecha de la pantalla hay
siempre un indicador, visible sobre cualquier aplicación y sin robar el foco ni los clics:
**● Activo** (verde), **● En pausa** (amarillo), **● Sin rostro** (rojo), **Detenido** o
**Activo, cursor desactivado**. Cada gesto reconocido destella en el indicador con su acción
(«✔ Clic izquierdo») y suena un aviso. La pausa tiene su propio sonido y cartel (P3-19). En
la pestaña **Avisos** se puede desactivar el sonido (los destellos siguen) o el indicador.

**Recordatorios de descanso (P3-45).** En **Avisos** se activa el recordatorio y su intervalo
(1–180 min de uso; 30 por defecto). Solo cuenta el tiempo con el control activo y el rostro
visible; una pausa de 2 minutos o más cuenta como descanso y reinicia la cuenta. El aviso
aparece arriba a la derecha con un sonido, no quita el foco, no pausa el control y se cierra
solo a los 20 s. **Probar aviso de descanso** lo muestra al momento.

**Estilo visual y modo oscuro.** La aplicación usa el lenguaje visual de la landing: fondo
crema `#f3efe6`, tarjetas blancas `#ffffff` redondeadas, tinta `#13171c` y el naranja de marca
`#ff6a2b` en botones principales, pestañas activas, interruptores y deslizadores. El
interruptor **Modo oscuro** de la cabecera cambia toda la aplicación al instante (también el
teclado y el menú rápido) y se guarda en el perfil; *Restaurar valores* no lo cambia. El
asistente de calibración es siempre oscuro, para concentrarse en la instrucción. Contraste
WCAG 2.1 AA (texto ≥ 4,5:1, comprobado en las pruebas): como el naranja da 2,9:1 con el
blanco, el texto sobre él es tinta y el texto naranja en modo claro usa el tono `#b93c0d`.

Los perfiles existentes conservan su mapeo. Para usar el nuevo, pulse **Restaurar valores** y
luego **Calibrar** (los guiños venían desactivados y no estaban calibrados).

Los perfiles creados en el Sprint 2 se cargan sin problema, pero «Fruncir los labios» aparece
*Sin calibrar*: pulse **Calibrar** una vez para incluirlo.

### Crear el instalador (P3-24)

La etapa **4. CD** del workflow [CI/CD GestIA](.github/workflows/ci-cd.yml) lo hace en GitHub
(Windows, Python 3.12) solo si pasaron las pruebas y los controles de seguridad: descarga del
modelo, ejecutable con PyInstaller (`packaging/gestia.spec`) e instalador con Inno Setup
(`packaging/installer.iss`). Cada push a `main` deja el instalador como artefacto de la
ejecución. Para publicar una versión:

1. Actualice `version` en `pyproject.toml` (por ejemplo `0.7.0`) y únalo a `main`.
2. Cree y suba el tag con la misma versión:

   ```powershell
   git tag v0.7.0
   git push origin v0.7.0
   ```

3. Al terminar el workflow, la Release `v0.7.0` tendrá `GestIA-Setup.exe` y el botón de la
   landing descargará esa versión (siempre apunta a `releases/latest`).

Para probar una rama sin publicar: *Actions → CI/CD GestIA → Run workflow*, elegir la rama, y
descargar el instalador de los artefactos de esa ejecución. En local (Windows, Python 3.12 y [Inno Setup 6](https://jrsoftware.org/isinfo.php)):

```powershell
python -m pip install . pyinstaller==6.11.1
python tools/download_model.py
pyinstaller packaging/gestia.spec --noconfirm
iscc /DAppVersion=0.7.0 packaging/installer.iss
```

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
ruff format --check .
pytest
pytest --cov   # con reporte de cobertura (mínimo 70 %)
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

## Integración y entrega continuas (CI/CD) y seguridad

Cada pull request, cada push a `main` y cada tag `vX.Y.Z` ejecutan el workflow
[CI/CD GestIA](.github/workflows/ci-cd.yml) por etapas; cada una corre solo si la anterior pasó:

```
1. Lint y SAST ──► 2. Pruebas (Python 3.11 y 3.12) ──────┐
               ├─► 3. Seguridad: dependencias (pip-audit) ┼─► 4. CD: instalador de Windows
               └─► 3. Seguridad: secretos (gitleaks) ─────┘
```

En los pull requests la etapa 4 se omite. En `main` deja el instalador como artefacto y con un
tag lo publica en GitHub Releases (sección «Crear el instalador»). Los controles:

| Control | Herramienta | Qué bloquea |
|---|---|---|
| Estilo y formato | `ruff check .`, `ruff format --check .` | Errores de estilo o código sin formatear |
| Pruebas y cobertura (P3-67) | `pytest -m "not camara and not modelo" --cov` | Cualquier prueba fallida o cobertura menor al 70 % (`fail_under` en `pyproject.toml`). El resumen de cada ejecución muestra la cobertura y el reporte HTML queda como artefacto |
| Privacidad (P3-27) | `tests/test_privacidad.py` | Código que guarde imágenes o video, conexiones a internet fuera de `license.py` o datos enviados que no sean correo, contraseña o equipo |
| Código inseguro (SAST, P3-59) | Reglas `S` de ruff (equivalentes a Bandit) | Cualquier hallazgo; las excepciones van por línea con `# noqa: Sxxx` y su motivo |
| Dependencias (P3-56) | `pip-audit` en Windows con Python 3.12 | Cualquier vulnerabilidad conocida no documentada |
| Secretos (P3-57) | `gitleaks` sobre todo el historial (en Ubuntu) | Cualquier clave, token o contraseña |

Las pruebas que necesiten la cámara o el modelo descargado se marcan con
`@pytest.mark.camara` o `@pytest.mark.modelo` y el CI las excluye.

**Excepciones de dependencias.** `pip-audit` no informa la gravedad, así que todo aviso falla
el CI. Si una vulnerabilidad no tiene corrección compatible, se documenta en
[.github/pip-audit-excepciones.txt](.github/pip-audit-excepciones.txt) con su ID, el motivo y
la fecha de revisión. **Dependabot** ([.github/dependabot.yml](.github/dependabot.yml)) abre
cada lunes PRs con las actualizaciones de librerías y de acciones de GitHub.

**Secretos en local (P3-57).** Para que gitleaks revise cada commit antes de crearlo, instale
el hook una vez por clon (la primera ejecución descarga gitleaks y tarda un poco):

```powershell
pip install -e ".[dev]"
pre-commit install
```

Si bloquea un commit, quite el secreto del archivo (por ejemplo, páselo a `config.json`, que
Git ignora). Los falsos positivos se documentan en [.gitleaks.toml](.gitleaks.toml) con su
motivo. Si un secreto real llegó a subirse: primero revóquelo en el servicio y después
límpielo del historial.

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
- `profiles.py`: perfiles JSON, su almacén, exportación e importación.
- `app_context.py`: aplicación en primer plano y aplicaciones abiertas (API de Windows).
- `control.py`: control del puntero (filtro One Euro, zona muerta, clics, permanencia,
  arrastre, desplazamiento, pausa) y backend pynput.
- `keyboard.py`: teclado virtual (distribuciones, teclas especiales, atajos, frases) y backend
  pynput.
- `quick_actions.py`: acciones rápidas del sistema (atajos de ventanas y abrir aplicaciones)
  y backend pynput.
- `prediction.py`, `lexicon_es.py`: predicción de palabras con diccionario local y aprendizaje.
- `feedback.py`: estado que muestra el indicador, sonidos y temporizador de descanso.
- `theme.py`: paleta de marca (modo claro y oscuro) y hojas de estilo de toda la interfaz.
- `paths.py`: carpetas en desarrollo e instalada (programa y datos de la persona).
- `autostart.py`: inicio automático con Windows (clave Run del usuario).
- `tutorial.py`, `ui_tutorial.py`: lecciones del tutorial y modo de práctica, y su ventana.
- `packaging/`: ejecutable (PyInstaller), instalador (Inno Setup) e ícono.
- `ui_calibration.py`, `ui_profile.py`, `ui_widgets.py`, `ui_keyboard.py`,
  `ui_quick_menu.py`: asistente, panel de gestos, puntero virtual, ventana del teclado y menú de
  acciones rápidas.

Flujo de datos: `capture` → `vision` (landmarks) → `tracking` (estado) → `features` →
`gestures` (en el hilo del worker) → `DisplayPacket` → `ui` (vista, asistente, recentrado,
perfil) → `control` (cursor del sistema).

Calibración, gestos, comandos y adaptador del SO se incorporarán cuando tengan comportamiento
real, sin crear módulos vacíos. No se crea ni publica ningún repositorio remoto en este sprint.

Fuentes: [guía oficial de Face Landmarker](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/python),
[modelo oficial](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/index)
y [MediaPipe 0.10.21](https://pypi.org/project/mediapipe/0.10.21/).
