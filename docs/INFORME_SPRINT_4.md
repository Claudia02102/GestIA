# Informe breve — Sprint 4 (Épica E4: Escritura en pantalla)

## Implementado

- **`keyboard.py`**: `TypingSession`, lógica pura del teclado: escribe en la aplicación activa
  mediante un `KeyboardBackend` y lleva la palabra en curso para la predicción. Backend real
  con `pynput` (SendInput en Windows, admite ñ y tildes). Ajustes del teclado por perfil.
- **`prediction.py`** + **`lexicon_es.py`**: predicción local en español.
- **`ui_keyboard.py`**: ventana flotante siempre encima que **no toma el foco** (en Windows,
  `WS_EX_NOACTIVATE`). Se maneja con el cursor de la cabeza y los gestos de clic, o con el
  clic por permanencia del Sprint 3.
- **HU-19 (P3-39) Teclado virtual**: letras, ñ, números, tildes y signos españoles; botón
  **Mostrar teclado** en la ventana principal. Se oculta durante el asistente de calibración.
- **HU-20 (P3-40) Predicción**: tres sugerencias según las primeras letras, sin importar
  tildes ni mayúsculas («esta» → «está»). Respeta mayúsculas iniciales. Elegir una completa
  la palabra y añade un espacio. Las palabras escritas se aprenden: una nueva se sugiere desde
  la segunda vez. Solo se guardan palabras sueltas y su conteo (máximo 2000), con botón para
  olvidarlas.
- **HU-21 (P3-41) Teclas especiales y atajos**: Intro, Borrar, Supr, Tab, Esc, flechas,
  Inicio, Fin, Mayús (una tecla), Bloq Mayús, y Ctrl+A/C/V/X/Z.
- **HU-22 (P3-42) Frases frecuentes**: lista por perfil con frases por defecto; se pueden
  añadir, editar, reordenar y eliminar (pestaña *Teclado*). Una selección escribe la frase.
- **HU-23 (P3-43) Teclado ajustable**: tamaño de tecla (32–140 px) y distribución QWERTY o
  alfabética. Si el tamaño no cabe, se usa el mayor que cabe en el área disponible; el
  teclado se coloca abajo y centrado. Se guarda en el perfil.
- Perfiles: nueva sección `keyboard` (esquema 3). Los perfiles anteriores siguen cargando.

## Validado sin hardware

72 pruebas automatizadas (17 nuevas): escritura, ñ y tildes, sugerencias en español,
completar con y sin tildes, aprendizaje tras dos usos, límites del vocabulario, Borrar y
flechas sobre la palabra en curso, Mayús/Bloq Mayús, atajos, frases, distribuciones, ajuste
a la pantalla y persistencia/compatibilidad de perfiles. Prueba de humo de la ventana Qt
(offscreen) con un teclado simulado: sugerencias, completar, frases y redimensionado.

## Pendiente / riesgos

- Llenar la [matriz de aceptación](MATRIZ_PRUEBAS_SPRINT_4.md) en Windows con webcam real.
- La palabra en curso solo se conoce por lo escrito con el teclado de GestIA: si se hace
  clic en otra parte del texto, la siguiente sugerencia puede basarse en letras anteriores
  hasta pulsar Espacio, Intro o una flecha.
- Windows no deja escribir en ventanas con privilegios de administrador (UIPI).
- Un gesto dedicado para mostrar/ocultar el teclado queda para la reasignación de gestos (E5).
- El diccionario base es breve (~500 palabras); puede ampliarse si las pruebas lo piden.
