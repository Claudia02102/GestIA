# Matriz de aceptación — Sprint 5 (Épica E5: Mapeo y personalización de comandos)

Estado: **pendiente de ejecución con webcam real**. Son pruebas de aceptación (caja negra):
no se automatizan en GitHub Actions porque necesitan una persona y una cámara. Antes de
empezar: perfil calibrado (tras *Restaurar valores*, pulse *Calibrar* para incluir los guiños).
Para recuperar el ratón en cualquier momento: **Ctrl+Alt+P**.

| HU (Jira) | Prueba de aceptación | Cómo ejecutarla | Resultado | Notas |
|---|---|---|---|---|
| HU-24 (P3-10) | Asignar un gesto a otra acción y comprobar que ejecuta la nueva | En *Mapeo*, dar a «Abrir la boca» la acción «Clic derecho»; abrir la boca sobre un archivo. | Pendiente | |
| HU-24 | Asignar un gesto ya usado advierte el conflicto | Dar a «Sonreír» la acción del guiño izquierdo: ambos intercambian (ver la tabla). | Pendiente | |
| HU-25 (P3-11) | Abrir el menú con un gesto y ver las acciones | Asignar «Acciones rápidas» a un gesto y hacerlo. | Pendiente | |
| HU-25 | «Cambiar de ventana» y «volver atrás» se ejecutan | Con dos ventanas y el navegador abiertos. | Pendiente | |
| HU-25 | Cerrar el menú sin elegir no ejecuta nada | Abrir y cerrar el menú. | Pendiente | |
| HU-26 (P3-16) | Mapeos distintos para navegador y procesador de textos | *Añadir aplicación* para ambos con acciones distintas; cambiar de ventana y repetir el gesto. | Pendiente | |
| HU-26 | Una aplicación sin mapeo usa el general | Repetir el gesto en el Bloc de notas. | Pendiente | |
| HU-27 (P3-17) | Exportar en un equipo e importar en otro con los mismos ajustes | *Exportar*, copiar el archivo, *Importar* en otro equipo y comparar pestañas. | Pendiente | |
| HU-27 | Un archivo inválido muestra error y no cambia nada | Importar un `.json` editado a mano con un valor roto. | Pendiente | |
| HU-28 (P3-18) | Restaurar devuelve mapeo y sensibilidad a sus valores iniciales | Cambiar sensibilidades y mapeo; *Restaurar valores* → *Sí*. | Pendiente | |
| HU-28 | Se pide confirmación antes de restaurar | *Restaurar valores* → *No*: nada cambia. | Pendiente | |
| P3-47 | El clic cae en el objetivo | Guiñar el ojo izquierdo sobre una casilla pequeña; abrir la boca (doble clic) sobre un archivo. | Pendiente | |
| P3-47 | Cerrar la boca no activa el desplazamiento | Abrir y cerrar la boca 10 veces: el modo desplazamiento no se activa. | Pendiente | |
| P3-47 | El cursor no se traba al girar la cabeza | Recorrer la pantalla de borde a borde sin guiñar. | Pendiente | |
