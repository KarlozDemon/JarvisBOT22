import discord
import edge_tts
import asyncio
import os
import re
import unicodedata
import random
import sqlite3
import pytz
from flask import Flask
import threading
from datetime import datetime

# ========================== CONFIGURACIÓN GENERAL ==============================
CANALES_OBJETIVO_IDS = [
    1375567307782357048,
    1383150424722509904
]
DB_FILE = "usuarios_frecuentes.db"

# ========================== UTILIDADES Y DATOS PERSISTENTES ====================

def inicializar_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS usuarios_frecuentes (
            guild_id INTEGER,
            user_id INTEGER,
            veces INTEGER,
            PRIMARY KEY (guild_id, user_id)
        )
    ''')
    conn.commit()
    conn.close()

def obtener_veces_usuario(guild_id, user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT veces FROM usuarios_frecuentes WHERE guild_id = ? AND user_id = ?', (guild_id, user_id))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def incrementar_veces_usuario(guild_id, user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    veces = obtener_veces_usuario(guild_id, user_id) + 1
    c.execute('REPLACE INTO usuarios_frecuentes (guild_id, user_id, veces) VALUES (?, ?, ?)', (guild_id, user_id, veces))
    conn.commit()
    conn.close()
    return veces

# ========================== FUNCIONES DE TEXTO Y SALUDOS =======================

NOMBRES_ESPECIALES = {
    "jose is back": "José",
    "jᴏꜱᴇ ɪꜱ ʙᴀᴄᴋ": "José"
}

frases_rapida = [
    "¡Vaya, {nombre}, eso sí fue una visita exprés!",
    "¡{nombre}, ni tiempo para un café! ¡Hasta luego!",
    "¡Relámpago, {nombre}! Entraste y saliste en un segundo.",
    "¡{nombre}, parpadeé y ya no estabas!",
    "¡{nombre}, ¿solo viniste a saludar? Qué fugaz!",
    "¡Eso sí fue un paso de cometa, {nombre}!",
    "¡Tu estadía fue tan rápida como la luz, {nombre}!",
    "¡{nombre}, el récord de velocidad es tuyo!",
    "¡Flash, {nombre}! ¡Casi ni te vimos!",
    "¡Eso sí fue llegar y salir, {nombre}!",
    "¡Entraste, {nombre}, y ya te extrañamos!",
    "¡{nombre}, seguro que estabas de paso!",
    "¡{nombre}, apenas llegaste y ya te vas!",
    "¡Pasada fugaz la tuya, {nombre}!",
    "¡Casi no alcanzamos a saludarte, {nombre}!",
    "¡Express total, {nombre}! Hasta la próxima.",
    "¡Rápido y curioso, {nombre}!",
    "¡Eso sí fue velocidad máxima, {nombre}!",
    "¡Sólo viniste a ver si había alguien, {nombre}?",
    "¡Tu conexión fue más corta que un meme, {nombre}!",
    "¡Pasaste como un suspiro, {nombre}!",    
    "¡La visita más rápida del día, {nombre}!",
    "¡{nombre}, ni la luz viaja tan rápido!",
    "¡Parecías un ninja, {nombre}!",
    "¡Te fuiste tan rápido como llegaste, {nombre}!",
    "¡Entrada y salida récord, {nombre}!",
    "¡Eso sí fue una visita flash, {nombre}!",
    "¡Ni los bots se desconectan tan rápido, {nombre}!",
    "¡Gracias por el micro saludo, {nombre}!",
    "¡Un hola y chau en tiempo récord, {nombre}!",
]

def limpiar_nombre(nombre):
    # Hardcode para casos especiales
    nombre_original = nombre.lower()
    if nombre_original in NOMBRES_ESPECIALES:
        return NOMBRES_ESPECIALES[nombre_original]

    # Paso 1: Normaliza el nombre a NFKC para juntar caracteres combinados y “fantasía”
    nombre = unicodedata.normalize('NFKC', nombre)

    # Paso 2: Elimina símbolos, emojis y puntuación, deja solo letras y números de cualquier idioma
    limpio = ""
    for c in nombre:
        categoria = unicodedata.category(c)
        # Letras (L*), números (N*), o espacios
        if categoria.startswith('L') or categoria.startswith('N') or c.isspace():
            limpio += c
    # Paso 3: Remueve espacios repetidos y capitaliza por palabra
    limpio = ' '.join(limpio.split())
    limpio = ' '.join(word.capitalize() for word in limpio.split())

    # Paso 4: Si queda vacío o muy corto, usa un apodo neutro
    if len(limpio) <= 2:
        return "Invitado"
    return limpio

def obtener_saludo_por_hora():
    zona_horaria = pytz.timezone('America/Lima')
    hora = datetime.now(zona_horaria).hour
    if 5 <= hora < 12:
        saludos = [
            "Buenos días",
            "¡Muy buenos días!",
            "¡Feliz mañana!",
            "¡Despierta con energía!",
            "¡Arranca el día con actitud!",
            "¡Qué gran día para empezar!",
            "¡Listos para un día genial!",
            "¡Aprovecha tu mañana!",
            "¡La mejor vibra para tu día!",
            "¡A sonreír que es de día!",
            "¡Café en mano y buena onda!",
            "¡Hoy es un gran día para lograrlo!",
            "¡Vamos que el día recién empieza!",
            "¡Empieza la jornada con optimismo!",
            "¡A romperla desde temprano!",
            "¡Brilla en este nuevo día!",
            "¡Que tengas una mañana llena de éxitos!",
            "¡Levántate y conquista el día!",
            "¡Dale con todo desde temprano!",
            "¡Hoy puede ser un gran día, aprovéchalo!",
            "¡Disfruta de cada minuto de esta mañana!",
            "¡Aprovecha la frescura de la mañana!",
            "¡Nada como empezar el día con amigos!",
            "¡Haz que esta mañana cuente!",
            "¡Energía positiva desde temprano!",
            "¡La mañana es tuya!",
            "¡Una sonrisa para empezar bien el día!",
            "¡Hoy pinta para ser un buen día!",
            "¡Que la luz de la mañana te acompañe!",
            "¡Mañana productiva para todos!",
        ]
    elif 12 <= hora < 19:
        saludos = [
            "Buenas tardes",
            "¡Excelente tarde!",
            "¡Que tengas una tarde increíble!",
            "¡A seguir con ganas esta tarde!",
            "¡Disfruta la tarde!",
            "¡Qué buena hora para conversar!",
            "¡La tarde se pone mejor contigo!",
            "¡Tarde soleada, ánimo a todos!",
            "¡Vamos por una gran tarde!",
            "¡Sigue brillando esta tarde!",
            "¡Que la tarde te rinda mucho!",
            "¡Tarde ideal para pasarla bien!",
            "¡El sol de la tarde trae buenas noticias!",
            "¡Disfruta esta tarde como se debe!",
            "¡Una tarde espectacular para todos!",
            "¡Hora de recargar energías y seguir!",
            "¡No hay nada como una tarde divertida!",
            "¡La mejor compañía para esta tarde eres tú!",
            "¡Haz de esta tarde algo especial!",
            "¡Vamos que aún queda mucho día!",
            "¡Anímate que la tarde recién comienza!",
            "¡Tarde de buenas vibras para ti!",
            "¡Un break en la tarde nunca viene mal!",
            "¡Que cada momento de esta tarde valga la pena!",
            "¡Gracias por alegrar la tarde!",
            "¡Tarde de risas y buena charla!",
            "¡Un saludo cálido en esta tarde!",
            "¡Día productivo, tarde feliz!",
            "¡Que la tarde te sorprenda gratamente!",
            "¡Tarde motivadora para todos!",
        ]
    else:
        saludos = [
            "Buenas noches",
            "¡Linda noche!",
            "¡Que descanses cuando termines!",
            "¡La noche es joven!",
            "¡Gran noche para conversar!",
            "¡Relájate y disfruta la noche!",
            "¡Aprovecha la calma de la noche!",
            "¡Noche tranquila para ti!",
            "¡A dormir luego de una buena charla!",
            "¡Que la noche te traiga paz!",
            "¡Dulces sueños cuando apagues la compu!",
            "¡Hora de relajarse y recargar pilas!",
            "¡Noche mágica para todos!",
            "¡Disfruta de la serenidad nocturna!",
            "¡Que la luna ilumine tu descanso!",
            "¡Finaliza el día con buenas vibras!",
            "¡Desconecta y prepárate para un gran mañana!",
            "¡Cierra el día con alegría!",
            "¡Noche de tranquilidad y buenos amigos!",
            "¡Gracias por compartir esta noche aquí!",
            "¡Ya casi hora de descansar!",
            "¡Que tus sueños sean geniales!",
            "¡Noche perfecta para charlar y reír!",
            "¡El canal nunca duerme, pero tú sí deberías!",
            "¡Aprovecha las últimas horas del día!",
            "¡Que la noche sea tan genial como tú!",
            "¡Recarga energía mientras descansas!",
            "¡Noche llena de paz y alegría!",
            "¡Apaga la compu, pero no la amistad!",
            "¡Gracias por acompañarnos esta noche!",
        ]
    return random.choice(saludos)

def obtener_frase_bienvenida(nombre, veces):
    ahora = datetime.now(pytz.timezone("America/Lima"))
    dia_semana = ahora.strftime("%A").lower()
    frases = []
    if dia_semana == "monday":
        frases.append(f"¡{nombre}, feliz lunes! Empecemos la semana con energía.")
    elif dia_semana == "friday":
        frases.append(f"¡{nombre}, ya es viernes! A relajarse.")
    elif dia_semana == "sunday":
        frases.append(f"¡{nombre}, aprovecha este domingo para descansar!")
    if veces == 1:
        frases += [
            f"¡Bienvenido, {nombre}! Siempre es un gusto recibir caras nuevas.",
            f"¡Qué emoción verte por primera vez hoy, {nombre}!",
            f"¡Hola, {nombre}! Tu primer acceso del día, espero que lo disfrutes.",
            f"¡Increíble verte aquí, {nombre}! Esta es tu bienvenida especial.",
            f"¡{nombre}, recién llegas y ya se siente la diferencia!",
            f"¡La sala se alegra con tu primera entrada, {nombre}!",
            f"¡Estrenando presencia, {nombre}! Buen día.",
            f"¡Arranca el día con buena vibra, {nombre}!",
            f"¡Espero que tu primer rato aquí sea el mejor, {nombre}!",
            f"¡{nombre}, bienvenido oficialmente a la conversación de hoy!",
            f"¡Aplausos para {nombre}, quien debuta en el canal hoy!",
            f"¡Hola, {nombre}! Que tengas la mejor de las experiencias.",
            f"¡Hoy es especial, {nombre} llegó por primera vez!",
            f"¡{nombre}, eres la novedad del día!",
            f"¡La jornada empieza bien si te tenemos aquí, {nombre}!",
            f"¡Bienvenido al mejor canal, {nombre}!",
            f"¡Un nuevo día, una nueva bienvenida para ti, {nombre}!",
            f"¡Hoy el canal estrena energía con tu llegada, {nombre}!",
            f"¡Qué suerte tenerte, {nombre}, en tu primer acceso!",
            f"¡Primer visita del día, {nombre}! Hazla memorable.",
            f"¡{nombre}, la bienvenida siempre es especial para ti!",
            f"¡Arrancamos la diversión con tu llegada, {nombre}!",
            f"¡{nombre}, disfruta tu estadía desde este momento!",
            f"¡El día mejora con tu primer acceso, {nombre}!",
            f"¡Toma asiento, {nombre}, y siéntete como en casa!",
            f"¡El canal se inaugura contigo, {nombre}!",
            f"¡Es un honor recibirte, {nombre}!",
            f"¡{nombre}, gracias por empezar tu día con nosotros!",
            f"¡Tu primera conexión promete buenos momentos, {nombre}!",
            f"¡Aquí te recibe tu nueva familia virtual, {nombre}!",
            f"¡Bienvenido al club de los geniales, {nombre}!",
            f"¡Un nuevo inicio con la llegada de {nombre}!",
            f"¡{nombre}, que tu paso por aquí sea legendario!",
            f"¡Démosle la bienvenida a {nombre}, la estrella del día!",
            f"¡{nombre}, la diversión te espera desde ya!",
            f"¡Primer acceso, primer saludo para {nombre}!",
            f"¡Hoy tenemos estreno de lujo: {nombre} en el canal!",
            f"¡Ya era hora de verte, {nombre}! Disfruta tu primer acceso.",
            f"¡Con tu llegada, {nombre}, empieza lo bueno!",
            f"¡Bienvenido a tu nuevo espacio favorito, {nombre}!",
            f"¡La conversación arranca con broche de oro, {nombre}!",
            f"¡{nombre}, que este sea el primero de muchos ingresos!",
            f"¡Sientete bienvenido en cada palabra, {nombre}!",
            f"¡Gracias por visitarnos, {nombre}! Hoy es tu día.",
            f"¡Una bienvenida enorme para ti, {nombre}!",
            f"¡Disfruta el canal, {nombre}, está hecho para ti!",
            f"¡Hoy eres el invitado especial, {nombre}!",
            f"¡Todo es mejor cuando aparece {nombre}!",
            f"¡Primer día, primer saludo, {nombre}!",
            f"¡{nombre}, que empiece la buena vibra!",
        ]
    elif veces == 2:
        frases += [
            f"¡Ya de vuelta, {nombre}! Me alegra verte tan seguido.",
            f"¡{nombre}, la segunda vez siempre es mejor!",
            f"¡Parece que te gustó, {nombre}, volviste rápido!",
            f"¡Bien ahí, {nombre}, ya vas por la segunda ronda!",
            f"¡{nombre}, repitiendo la dosis de buena onda!",
            f"¡Eres constante, {nombre}! Segunda visita del día.",
            f"¡Otra vez juntos, {nombre}! Esto se pone bueno.",
            f"¡Segundo turno para ti, {nombre}!",
            f"¡{nombre}, tu frecuencia es digna de un VIP!",
            f"¡Doble presencia, {nombre}! Eso sí es dedicación.",
            f"¡Hoy toca doblete, {nombre}!",
            f"¡{nombre}, el día mejora porque volviste!",
            f"¡Qué alegría verte dos veces, {nombre}!",
            f"¡Segunda entrada triunfal para {nombre}!",
            f"¡La costumbre hace al campeón, {nombre}!",
            f"¡Bienvenido de nuevo, {nombre}!",
            f"¡Esta segunda visita promete, {nombre}!",
            f"¡{nombre}, lo bueno se repite!",
            f"¡No se puede tener suficiente de ti, {nombre}!",
            f"¡Tenerte dos veces es doble alegría, {nombre}!",
            f"¡{nombre}, ya eres habitual!",
            f"¡Gracias por regresar, {nombre}!",
            f"¡Segunda vuelta, doble diversión, {nombre}!",
            f"¡{nombre}, tu segunda entrada ilumina el canal!",
            f"¡Dos veces en un día, {nombre}! Eso es pasión.",
            f"¡Aquí vamos de nuevo, {nombre}!",
            f"¡Tu segunda aparición es lo máximo, {nombre}!",
            f"¡{nombre}, siempre bienvenido, siempre feliz de verte!",
            f"¡Hoy hay revancha y tú lo sabes, {nombre}!",
            f"¡Gracias por tu constancia, {nombre}!",
            f"¡{nombre}, parece que te enganchaste con el canal!",
            f"¡Nos alegra tenerte de vuelta, {nombre}!",
            f"¡Volviste antes de lo esperado, {nombre}!",
            f"¡No podías resistir regresar, {nombre}!",
            f"¡Eres la excepción a la regla, {nombre}!",
            f"¡La comunidad te agradece el doble, {nombre}!",
            f"¡Te echamos de menos, {nombre}, aunque fuera un ratito!",
            f"¡{nombre}, segunda visita, doble diversión!",
            f"¡Tu regreso es motivo de celebración, {nombre}!",
            f"¡Tenerte aquí dos veces es todo un lujo, {nombre}!",
            f"¡{nombre}, el canal es tuyo, entra cuantas veces quieras!",
            f"¡Bien por ti, {nombre}, segunda ronda de buena vibra!",
            f"¡Esto sí es afición, {nombre}!",
            f"¡El canal se alegra cada vez que entras, {nombre}!",
            f"¡Otra vez por aquí, {nombre}!",
            f"¡Te nos volviste a aparecer, {nombre}!",
            f"¡Eres incansable, {nombre}!",
            f"¡Nos vemos seguido hoy, {nombre}!",
            f"¡{nombre}, la reincidencia está permitida!",
            f"¡Sigue sumando, {nombre}!",
        ]      
    elif veces == 3:
        frases += [
            f"¡La tercera es la vencida, {nombre}! Bienvenido otra vez.",
            f"¡Eres el alma de este canal hoy, {nombre}!",
            f"¡Tercera visita y contando, {nombre}!",
            f"¡Wow, {nombre}, hoy sí que eres habitual!",
            f"¡Ya pareces moderador, {nombre}!",
            f"¡Esto ya es costumbre, {nombre}!",
            f"¡Tercera ronda, {nombre}! Increíble energía.",
            f"¡Eres más regular que el bot, {nombre}!",
            f"¡El récord del día va para ti, {nombre}!",
            f"¡{nombre}, la triple entrada no es para cualquiera!",
            f"¡Otra vez tú, {nombre}! Nos encanta verte tan seguido.",
            f"¡Tercera vez, tercer saludo para {nombre}!",
            f"¡{nombre}, ¿andas buscando premio por constancia?",
            f"¡Hoy es tu día de romper marcas, {nombre}!",
            f"¡Este canal ya tiene tu nombre, {nombre}!",
            f"¡Nadie visita tanto como tú, {nombre}!",
            f"¡{nombre}, la costumbre es buena cuando eres tú!",
            f"¡Hoy nadie te iguala, {nombre}!",
            f"¡Tres veces, tres razones para alegrarnos, {nombre}!",
            f"¡Gracias por volver, volver y volver, {nombre}!",
            f"¡¿Tercera vez?! Aquí sí que te gusta, {nombre}!",
            f"¡Eres parte del inventario del canal hoy, {nombre}!",
            f"¡No hay dos sin tres, {nombre}!",
            f"¡Tercera aparición estelar, {nombre}!",
            f"¡Tres veces mejor, {nombre}!",
            f"¡Nadie te gana hoy en visitas, {nombre}!",
            f"¡{nombre}, deberías cobrar alquiler por tantas visitas!",
            f"¡El canal tiene tu huella, {nombre}!",
            f"¡¿Tres veces ya?! Eso sí es entusiasmo, {nombre}!",
            f"¡Hoy eres la figura del día, {nombre}!",
            f"¡Si entras una más, te hacemos admin, {nombre}!",
            f"¡Tercera vez y seguimos sumando, {nombre}!",
            f"¡Triple alegría con tu presencia, {nombre}!",
            f"¡Así se hace, {nombre}, tres veces campeón!",
            f"¡El canal te agradece el récord, {nombre}!",
            f"¡{nombre}, eres el visitante estrella hoy!",
            f"¡Tres veces es todo un logro, {nombre}!",
            f"¡Sigue así, {nombre}, vas por buen camino!",
            f"¡Nos hace felices verte tan constante, {nombre}!",
            f"¡Tu energía nunca se acaba, {nombre}!",
            f"¡Nadie repite como tú, {nombre}!",
            f"¡No te canses, {nombre}, eres bienvenido siempre!",
            f"¡Ya es costumbre saludarte seguido, {nombre}!",
            f"¡Qué motivación la tuya, {nombre}!",
            f"¡El récord de hoy es tuyo, {nombre}!",
            f"¡No pares, {nombre}, el canal te quiere!",
            f"¡Tres veces, tres aplausos para ti, {nombre}!",
            f"¡Por ti el canal sigue con vida, {nombre}!",
            f"¡Así se forjan las leyendas, {nombre}!",
            f"¡Tercera y no última, seguro, {nombre}!",
        ]
    else:
        frases += [
            f"¡{nombre}, perdiste la cuenta de tantas visitas!",
            f"¡{nombre}, parece que hoy te quedas a vivir aquí!",
            f"¡{nombre}, ya eres parte del mobiliario del canal!",
            f"¡Esto sí es dedicación, {nombre}! Ya ni sé cuántas veces vas.",
            f"¡El canal no es lo mismo sin ti, {nombre}, aunque sea la visita {veces}!",
            f"¡Hoy rompiste tu propio récord, {nombre}!",
            f"¡{nombre}, tu constancia es admirable!",
            f"¡No puedo creerlo, {nombre}, {veces} visitas en un solo día!",
            f"¡Wow, {nombre}! Hoy eres VIP total.",
            f"¡La sala lleva tu nombre, {nombre}, después de {veces} veces!",
            f"¡{nombre}, ¿duermes aquí o qué?!",
            f"¡Tu nombre debería estar en la entrada del canal, {nombre}!",
            f"¡Rompiste la matrix del canal, {nombre}!",
            f"¡Eres leyenda viva, {nombre}, {veces} visitas hoy!",
            f"¡Nadie te iguala, {nombre}! Tu presencia es inigualable.",
            f"¡Nos acostumbramos a verte cada rato, {nombre}!",
            f"¡El récord mundial es tuyo, {nombre}!",
            f"¡{nombre}, el canal ya no es lo mismo sin ti!",
            f"¡Eres el usuario más activo del día, {nombre}!",
            f"¡Tu entusiasmo no tiene comparación, {nombre}!",
            f"¡{veces} visitas en un solo día! Eso es dedicación, {nombre}.",
            f"¡Cada vez que entras sube el rating, {nombre}!",
            f"¡El canal te agradece tanto tiempo, {nombre}!",
            f"¡Hoy no paramos hasta que {nombre} se canse!",
            f"¡Hoy eres la estrella indiscutible, {nombre}!",
            f"¡Si esto fuera un juego, ya ganaste el logro de visitas, {nombre}!",
            f"¡Tus visitas son el motor del canal, {nombre}!",
            f"¡Esto ya es maratón, {nombre}!",
            f"¡El día es más divertido contigo, {nombre}!",
            f"¡A este paso, te haces moderador, {nombre}!",
            f"¡Gracias por tanta actividad, {nombre}!",
            f"¡{nombre}, te has ganado el título de 'insoportable'! (con cariño)",
            f"¡Vas a romper el bot con tantas visitas, {nombre}!",
            f"¡Nadie ha visitado tanto como tú, {nombre}!",
            f"¡Que siga la fiesta con {nombre}!",
            f"¡Esto es un récord Guinness, {nombre}!",
            f"¡El canal te aclama, {nombre}!",
            f"¡Hoy eres el MVP, {nombre}!",
            f"¡Cualquier moderador ya estaría cansado, pero tú sigues, {nombre}!",
            f"¡No pares de entrar, {nombre}, nos motivas a todos!",
            f"¡Eres la referencia de perseverancia, {nombre}!",
            f"¡Ya deberíamos ponerte un emoji propio, {nombre}!",
            f"¡Impresionante tu constancia, {nombre}!",
            f"¡{nombre}, podrías cobrar entrada ya!",
            f"¡Hazte dueño del canal, {nombre}!",
            f"¡Tienes la llave del canal, {nombre}!",
            f"¡Eres la máquina de las visitas, {nombre}!",
            f"¡Te queremos aunque repitas mil veces, {nombre}!",
            f"¡Nadie más activo que tú, {nombre}!",
            f"¡Nunca es demasiado cuando se trata de {nombre}!",
        ]
    frases += [
        f"¡{nombre}, hoy el canal es más divertido contigo!",
        f"¡Siempre es mejor día cuando aparece {nombre}! {obtener_saludo_por_hora()}",
        f"¡{nombre}, tu energía alegra a todos en el canal!",
        f"¡Con {nombre} aquí, seguro hay buenas risas!",
        f"¡Qué bueno verte activo, {nombre}!",
        f"¡{nombre}, esperamos que tengas un gran rato con nosotros!",
        f"¡Nunca es lo mismo sin ti, {nombre}!",
        f"¡Hoy sí que promete, {nombre} está presente!",
        f"¡Arriba ese ánimo, {nombre}!",
        f"¡Disfruta mucho, {nombre}! {obtener_saludo_por_hora()}",
        f"¡{nombre}, llegaste justo cuando te necesitábamos!",
        f"¡{nombre}, este canal es tu segunda casa!",
        f"¡Gracias por sumarte, {nombre}!",
        f"¡Qué bueno verte conectando de nuevo, {nombre}!",
        f"¡{nombre}, siempre eres bienvenido!",
        f"¡Este lugar no sería igual sin ti, {nombre}!",
        f"¡{nombre}, quédate el tiempo que quieras!",
        f"¡Hoy va a ser épico porque {nombre} llegó!",
        f"¡{nombre}, la charla será mejor contigo aquí!",
        f"¡Hazte notar, {nombre}, el canal es tuyo!",
        f"¡{nombre}, aquí siempre hay lugar para ti!",
        f"¡Genial que estés aquí, {nombre}!",
        f"¡Saca tu mejor versión, {nombre}!",
        f"¡Vamos a pasarla increíble, {nombre}!",
        f"¡{nombre}, tú le das vida al canal!",
        f"¡No sabes cuánto te esperábamos, {nombre}!",
        f"¡Este canal necesitaba tu chispa, {nombre}!",
        f"¡Siempre hay un motivo para reír cuando estás, {nombre}!",
        f"¡A tu lado, cualquier conversación es interesante, {nombre}!",
        f"¡{nombre}, eres de los favoritos por aquí!",
        f"¡Que no falten tus comentarios, {nombre}!",
        f"¡Qué placer verte en línea, {nombre}!",
        f"¡Hoy va a ser legendario, {nombre}!",
        f"¡Tu llegada le pone sabor al canal, {nombre}!",
        f"¡{nombre}, eres parte esencial de la familia!",
        f"¡Cada vez que entras es fiesta, {nombre}!",
        f"¡El chat se activa cuando llegas, {nombre}!",
        f"¡Siempre se nota cuando {nombre} aparece!",
        f"¡Aquí nadie se aburre contigo, {nombre}!",
        f"¡No importa la hora, siempre eres bienvenido, {nombre}!",
        f"¡Que el buen humor no falte, {nombre}!",
        f"¡{nombre}, la charla mejora con tu presencia!",
        f"¡Espero que hoy traigas anécdotas, {nombre}!",
        f"¡Si hay alguien que anima el canal, es {nombre}!",
        f"¡Aquí te aplaudimos solo por estar, {nombre}!",
        f"¡Bienvenido al show, {nombre}!",
        f"¡Que tu día sea tan genial como tú, {nombre}!",
        f"¡Ya era hora de verte por aquí, {nombre}!",
        f"¡Ponte cómodo, {nombre}, esto apenas empieza!",
        f"¡Con {nombre} aquí, nadie se aburre!",
    ]
    return random.choice(frases)

def obtener_frase_despedida(nombre):
    frases = [
        f"¡Nos vemos, {nombre}! Descansa.",
        f"¡Chau {nombre}! ¡Pásala bien!",
        f"¡{nombre}, cuídate mucho! ¡Hasta la próxima!",
        f"¡{nombre}, vuelve pronto! ¡Me alegra verte siempre!",
        f"¡Hasta luego, {nombre}! ¡Éxitos en tu día!",
        f"¡{nombre}, el canal te extrañará!",
        f"¡{nombre}, la próxima ronda de memes será por ti!",
        f"¡Hasta pronto, {nombre}! Tu silla te esperará.",
        f"¡{nombre}, que la fuerza te acompañe hasta la próxima!",
        f"¡Desconectando a {nombre}! Vuelve pronto.",
        f"¡{nombre}, gracias por pasar, no tardes en volver!",
        f"¡Ya se siente el silencio sin ti, {nombre}!",
        f"¡{nombre}, tu energía se queda aquí hasta que regreses!",
        f"¡Haz una pausa y vuelve cuando quieras, {nombre}!",
        f"¡{nombre}, el chat será menos divertido sin ti!",
        f"¡Listo, {nombre}! Hora de recargar energías.",
        f"¡Espero verte de nuevo pronto, {nombre}!",
        f"¡No te olvides de nosotros, {nombre}!",
        f"¡Ve tranquilo, {nombre}! Aquí te esperamos.",
        f"¡{nombre}, apaga la compu pero no la amistad!",
        f"¡Nos vemos en la próxima aventura, {nombre}!",
        f"¡{nombre}, se cierra el telón hasta tu regreso!",
        f"¡{nombre}, que tengas una excelente jornada!",
        f"¡Hasta la vista, {nombre}!",
        f"¡Bye bye, {nombre}! Vuelve con historias nuevas.",
        f"¡{nombre}, no te pierdas mucho!",
        f"¡Fue un gusto compartir contigo, {nombre}!",
        f"¡{nombre}, hasta el próximo meme!",
        f"¡{nombre}, te veremos en los créditos finales!",
        f"¡No es un adiós, es un hasta luego, {nombre}!",
        f"¡{nombre}, tu ausencia será notada!",
        f"¡Que descanses, {nombre}! Recarga baterías.",
        f"¡{nombre}, nos vemos en el próximo episodio!",
        f"¡{nombre}, la próxima vez trae snacks!",
        f"¡Cerrando sesión, {nombre}… vuelve pronto!",
        f"¡Que la buena vibra te acompañe, {nombre}!",
        f"¡Fue genial tenerte aquí, {nombre}!",
        f"¡{nombre}, dale saludos a la familia!",
        f"¡{nombre}, el grupo se queda más callado sin ti!",
        f"¡Nos leemos luego, {nombre}!",
        f"¡No olvides volver, {nombre}!",
        f"¡{nombre}, nos haces falta ya!",
        f"¡Hasta otro día épico, {nombre}!",
        f"¡Descansa la voz, {nombre}!",
        f"¡Que sueñes bonito, {nombre}!",
        f"¡Nos vemos en el próximo raid, {nombre}!",
        f"¡Cualquier cosa, aquí estamos, {nombre}!",
        f"¡Acuérdate de las buenas vibras, {nombre}!",
        f"¡Ya tienes excusa para regresar, {nombre}!",
        f"¡Hoy el canal pierde brillo porque te vas, {nombre}!",
        f"¡Que el WiFi siempre esté de tu lado, {nombre}!",
    ]
    return random.choice(frases)

# ========================== FUNCIONES DE AUDIO (TTS) ===========================

guild_locks = {}
entradas_usuarios = {}

async def play_audio(vc, text):
    if vc.guild.id not in guild_locks:
        guild_locks[vc.guild.id] = asyncio.Lock()
    lock = guild_locks[vc.guild.id]
    filename = f"tts_{vc.guild.id}.mp3"
    try:
        async with lock:
            print(f"[AUDIO] {vc.guild.name}: {text}")
            communicate = edge_tts.Communicate(text, voice="es-ES-ElviraNeural")
            await communicate.save(filename)
            vc.play(discord.FFmpegPCMAudio(filename, executable="ffmpeg", options='-filter:a "volume=2.0"'))
            while vc.is_playing():
                await asyncio.sleep(1)
            await asyncio.sleep(1)
    except Exception as e:
        print(f"[ERROR] Reproduciendo audio: {e}")
    finally:
        try:
            if os.path.exists(filename):
                os.remove(filename)
        except Exception as e:
            print(f"[ERROR] No se pudo borrar el archivo temporal {filename}: {e}")

# ========================== DISCORD SETUP Y EVENTOS ============================

intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True
intents.members = True

bot = discord.Client(intents=intents)

@bot.event
async def on_ready():
    print(f"JarvisTeamProSQL está online ✅\nUsuario: {bot.user} | ID: {bot.user.id}")

@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return
    nombre_limpio = limpiar_nombre(member.display_name)
    voice_client = discord.utils.get(bot.voice_clients, guild=member.guild)
    ahora = datetime.now(pytz.timezone("America/Lima"))

    # === Evento de ENTRADA ===
    if after.channel and after.channel.id in CANALES_OBJETIVO_IDS and (before.channel != after.channel):
        perms = after.channel.permissions_for(member.guild.me)
        if not perms.connect or not perms.speak:
            print(f"[PERMISOS] No puedo conectar/hablar en: {after.channel.name}")
            return

        # --- Gestión con base de datos ---
        veces = incrementar_veces_usuario(member.guild.id, member.id)

        print(f"[ENTRADA] {nombre_limpio} entró en {after.channel.name} (veces hoy: {veces})")
        if voice_client is None or not voice_client.is_connected():
            try:
                voice_client = await after.channel.connect()
            except Exception as e:
                print(f"[ERROR] No pude conectar al canal de voz: {e}")
                return
       
        entradas_usuarios[(member.guild.id, member.id)] = ahora

        text = obtener_frase_bienvenida(nombre_limpio, veces)
        num_usuarios = len([m for m in after.channel.members if not m.bot])
        if num_usuarios >= 20:
            text = f"¡Wow, esto se está llenando! Bienvenido {nombre_limpio}, y saludos a todos los presentes."
        await play_audio(voice_client, text)

    # === Evento de SALIDA ===
    if before.channel and before.channel.id in CANALES_OBJETIVO_IDS and after.channel != before.channel:
        print(f"[SALIDA] {nombre_limpio} salió de {before.channel.name}")
        if voice_client and voice_client.is_connected():
            entrada = entradas_usuarios.pop((member.guild.id, member.id), None)
            if entrada:
                duracion = (ahora - entrada).total_seconds()
                if duracion < 10:
                    text = random.choice(frases_rapida).format(nombre=nombre_limpio)
                else:
                    text = obtener_frase_despedida(nombre_limpio)
            else:
                text = f"{nombre_limpio} se ha desconectado. ¡Cuídate!"
            await play_audio(voice_client, text)

        # === Desconexión inteligente ===
        if voice_client and voice_client.is_connected() and voice_client.channel:
            usuarios_humanos = [m for m in voice_client.channel.members if not m.bot]
            if len(usuarios_humanos) == 1:
                unico = usuarios_humanos[0]
                text = f"{unico.display_name}, parece que ahora estás solo. ¡Aquí sigo contigo!"
                await play_audio(voice_client, text)
            elif not usuarios_humanos:
                text = "Parece que me quedé solito aquí…"
                await play_audio(voice_client, text)
                await voice_client.disconnect()

# ========================== SERVIDOR FLASK KEEP-ALIVE ==========================
app = Flask(__name__)

@app.route('/')
def index():
    return "¡Estoy vivo, Render! ✅"

def run_web():
    app.run(host='0.0.0.0', port=10000)

threading.Thread(target=run_web, daemon=True).start()

# ========================== INICIO DEL BOT =====================================
if __name__ == "__main__":
    inicializar_db()
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("❌ Error: La variable de entorno DISCORD_TOKEN no está definida.")
        exit(1)
    bot.run(TOKEN)
