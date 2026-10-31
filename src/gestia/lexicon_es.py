"""Palabras frecuentes del español, de la más a la menos usada (base de HU-20).

Lista breve y local: no requiere Internet. El orden fija la prioridad de las sugerencias.
"""

WORDS: tuple[str, ...] = tuple(
    """
de la que el en y a los se del las un por con no una su para es al lo como más pero sus le ya
o este sí porque esta entre cuando muy sin sobre también me hasta hay donde quien desde todo
nos durante todos uno les ni contra otros ese eso ante ellos e esto mí antes algunos qué unos
yo otro otras otra él tanto esa estos mucho quienes nada muchos cual poco ella estar estas
algunas algo nosotros mi mis tú te ti tu tus ellas nosotras vosotros vosotras os mío mía míos
mías tuyo tuya tuyos tuyas suyo suya suyos suyas nuestro nuestra nuestros nuestras vuestro
vuestra esos esas estoy estás está estamos estáis están esté estés estemos estén estaba estado
ser soy eres somos son era fue fueron sido será sería haber he has ha hemos han había habría
hacer hago hace hacen hizo hecho tener tengo tienes tiene tenemos tienen tenía tuve poder puedo
puedes puede podemos pueden podría decir digo dice dijo dicho ir voy vas va vamos van iba
ver veo ves ve visto dar doy da dado saber sé sabe querer quiero quieres quiere queremos llegar
llego llega pasar pasa deber debo debe poner pongo pone parecer parece quedar quedo queda creer
creo cree hablar hablo habla llevar llevo lleva dejar dejo deja seguir sigo sigue encontrar
llamar llamo llama venir vengo viene pensar pienso piensa salir salgo sale volver vuelvo vuelve
tomar tomo toma conocer conozco conoce vivir vivo vive sentir siento siente tratar mirar miro
mira contar cuento cuenta empezar esperar espero espera buscar busco busca existir entrar
trabajar trabajo trabaja escribir escribo escribe perder producir ocurrir entender entiendo
pedir pido pide recibir recordar recuerdo terminar permitir aparecer conseguir comenzar servir
sacar necesitar necesito necesita mantener resultar leer leo lee caer cambiar presentar crear
abrir abro abre considerar oír acabar convertir ganar formar traer partir morir aceptar
realizar suponer comprender lograr explicar preguntar tocar reconocer estudiar alcanzar nacer
dirigir correr utilizar pagar ayudar ayuda ayúdame gustar gusta jugar escuchar cumplir ofrecer
descubrir levantar intentar usar comer como come beber bebo dormir duermo descansar sentarse
año años vez veces día días tiempo vida casa mundo hombre mujer parte persona personas momento
forma lugar trabajo gobierno país caso mano manos cosa cosas noche semana mes hora horas punto
agua problema hijo hija padre madre familia amigo amiga nombre ciudad historia grupo cuerpo
palabra palabras cabeza ojos cara puerta mesa calle dinero escuela clase médico salud dolor
comida desayuno almuerzo cena baño cama teléfono computadora correo mensaje pantalla teclado
bien mal bueno buena buenos buenas mejor peor gran grande pequeño pequeña nuevo nueva viejo
mismo misma mismos primero primera último última todo toda todas cada otro poco pocos tan
siempre nunca ahora hoy mañana ayer tarde temprano luego después aquí allí ahí así entonces
mientras casi solo sólo además aunque menos tal según pues bastante demasiado
hola adiós gracias favor por perdón disculpa sí claro vale bueno listo
uno dos tres cuatro cinco seis siete ocho nueve diez cien mil
lunes martes miércoles jueves viernes sábado domingo
""".split()
)
