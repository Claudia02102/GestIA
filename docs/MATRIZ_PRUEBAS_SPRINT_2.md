# Matriz de aceptación — Sprint 2 (Épica E2)

Estado: **pendiente de ejecución con webcam real**. Registre fecha, equipo, cámara, luz y
persona (sin datos identificables). Use un perfil nuevo para cada persona.

| HU | Prueba de aceptación | Cómo ejecutarla en GestIA | Resultado | Notas |
|---|---|---|---|---|
| HU-06 | Completar el asistente solo con gestos | Perfil nuevo → Iniciar. El asistente se abre solo; completarlo sin tocar teclado ni ratón. | Pendiente | |
| HU-06 | Un paso mal hecho pide repetirlo | En «Giro a la derecha» girar otra vez a la izquierda, o no moverse 12 s. Debe aparecer «Repita el paso» e «intento 2». | Pendiente | |
| HU-06 | El cursor alcanza las cuatro esquinas | Paso final: llevar el puntero virtual a las cuatro esquinas (se ponen verdes). | Pendiente | El cursor real llega en E3 |
| HU-07 | Un gesto desactivado deja de reconocerse y no aparece en el mapeo | Desmarcar «Sonreír»; sonreír y ver que no aparece en *Eventos* ni en *Mapeo*. | Pendiente | |
| HU-07 | No se pueden desactivar todos los gestos de selección | Desmarcar «Abrir la boca» y luego «Sonreír» (guiños apagados): debe advertir y mantenerlo. | Pendiente | |
| HU-08 | Más sensibilidad: un gesto más sutil activa la acción | Con sensibilidad 3, abrir un poco la boca (barra a la mitad): sin evento. Subir a 8: el mismo gesto genera evento. | Pendiente | |
| HU-08 | Menos sensibilidad: el mismo gesto ya no la activa | Volver a 3 y repetir: sin evento. | Pendiente | |
| HU-08 | Se aplica sin reiniciar | Hacer los cambios anteriores con la cámara activa. | Pendiente | |
| HU-09 | La calibración se carga al reabrir | Calibrar, cerrar la app, reabrir: estado «Calibrado» y el asistente no se abre. | Pendiente | |
| HU-09 | Un ajuste modificado se conserva | Cambiar una sensibilidad, reiniciar y comprobarla. | Pendiente | |
| HU-10 | Recentrado en < 5 s | Cambiar de postura, levantar las cejas ~1 s y quedarse quieto. *Eventos* muestra «Puntero recentrado en X s» y el puntero queda al centro. | Pendiente | |
| HU-10 | El resto del perfil no cambia | Comparar gestos y sensibilidades antes y después (o el JSON del perfil). | Pendiente | |
| HU-11 | Dos perfiles conservan su calibración | Crear y calibrar «A» y «B»; alternar y verificar el puntero de cada uno. | Pendiente | |
| HU-11 | Cambiar de perfil aplica sus ajustes | Sensibilidades distintas en A y B; cambiar y ver los valores. | Pendiente | |
| HU-11 | Eliminar pide confirmación | Pulsar *Eliminar perfil*; responder *No* (se conserva) y luego *Sí*. | Pendiente | |

Anote también si fue necesario ajustar `calibration` en `config.json` y con qué valores.
