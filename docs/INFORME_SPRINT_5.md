# Informe breve — Sprint 5 (Épica E5: Mapeo y personalización de comandos)

Trabajo repartido entre los tres integrantes; cada historia se entregó como commits propios en
la rama `sprint-5` y se fusionó en `main` con un pull request.

## Implementado

- **HU-24 (P3-10) Mapeo de gestos a acciones**: selector de acción por gesto en la pestaña
  *Mapeo*. Reasignar una acción ya usada intercambia las acciones de ambos gestos, así nunca
  hay dos gestos con la misma. Siempre queda un gesto activo con clic izquierdo (o el clic por
  permanencia). El mapeo se guarda en el perfil.
- **HU-25 (P3-11) Menú de acciones rápidas** (`quick_actions.py`, `ui_quick_menu.py`): menú
  flotante que no toma el foco: cambiar de ventana, volver atrás, mostrar el escritorio, cerrar
  la ventana activa (con confirmación) y abrir Explorador, navegador, Bloc de notas o
  Calculadora. Se abre con un botón o con un gesto asignado a «Acciones rápidas».
- **HU-26 (P3-16) Mapeo por aplicación** (`app_context.py`): mapeos propios por ejecutable de
  la ventana activa; una aplicación sin mapeo propio usa el general. En pausa, el gesto general
  de pausa siempre reanuda.
- **HU-27 (P3-17) Exportar e importar**: el perfil completo se exporta a JSON y se importa como
  perfil nuevo sin sobrescribir ninguno. Un archivo inválido, enorme o con valores no finitos se
  rechaza sin cambiar nada.
- **HU-28 (P3-18) Restaurar valores por defecto**: botón con confirmación; gestos,
  sensibilidad, mapeo (y mapeos por aplicación), puntero y teclado vuelven a su valor inicial.
  Se conservan nombre, calibración, frases y palabras aprendidas. Avisa si queda activo un
  gesto sin calibrar.
- **Error P3-47** (clic con «abrir la boca» fuera del objetivo): abrir la boca baja el mentón y
  desviaba la inclinación medida; al cerrarla, los labios juntos activaban el desplazamiento.
  Los clics pasan a los guiños (izquierdo y derecho), el cursor se fija mientras se forma un
  gesto de la boca con clic o arrastre, y los gestos de la boca esperan 600 ms entre sí.
- Perfiles: esquema 4 (`app_actions`). Los perfiles anteriores siguen cargando con su mapeo.

## Pruebas por fases en GitHub Actions

Se separaron las pruebas en `tests/unit`, `tests/integration`, `tests/system` y
`tests/complementarias`, y se añadió el workflow `.github/workflows/pruebas.yml`
(detalle en la sección *Pruebas y CI* del README). Resultado local: **150 pruebas, todas
pasan**, en Python 3.11 y 3.12; cobertura del 78 % con todas las fases (68 % solo con
unitarias e integración, mínimo exigido 65 %). La inferencia de MediaPipe sobre la foto de
prueba tarda ~8 ms (presupuesto de HU-05: 66 ms).

## Pendiente / riesgos

- Llenar la [matriz de aceptación](MATRIZ_PRUEBAS_SPRINT_5.md) con webcam y personas reales.
- Confirmar con personas que los guiños son cómodos como clic principal; si no, cualquier
  persona puede reasignarlos en *Mapeo*.
- Los perfiles creados antes de P3-47 conservan el mapeo antiguo hasta pulsar *Restaurar
  valores* (y *Calibrar* para los guiños).
- `pip-audit` reporta avisos de `protobuf` 4.25, exigido por MediaPipe 0.10.21.
- Medir la inclinación con puntos que no dependan de la mandíbula eliminaría la causa de raíz
  de P3-47, pero obliga a recalibrar todos los perfiles.
