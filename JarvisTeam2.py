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
    1383150424722509904, # WolfTeam 24/7 - Clan2 Voz
    1375567307782357048, # PiscoSour™ - Team2 Voz
    1381032704124125226, # NyxLeyendasWT - Otros Games
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
    "José is back": "José",
    "jᴏꜱᴇ ɪꜱ ʙᴀᴄᴋ": "José"
}

frases_rapida = [
    "¡Vaya, {nombre}, eso sí fue una visita rápida!",
    "¡{nombre}, ni tiempo para hablar! ¡Hasta luego!",
    "¡{nombre}, entraste y saliste en un segundo!",
    "¡{nombre}, parpadeé y ya no estabas!",
    "¡{nombre}, ¿solo viniste a saludar? ¡Te fuiste!",
    "¡Entraste, {nombre}! ¡Casi ni te vimos!",
    "¡Eso sí fue llegar y salir, {nombre}!",
    "¡Entraste, {nombre}, y ya te fuiste!",
    "¡{nombre}, apenas llegaste y ya te vas!",
    "¡Te fuiste tan rápido como llegaste, {nombre}!",
]

frases_inicio_stream = [
    "¡{nombre} está transmitiendo, a mirar ese talento con aimbot!",
    "¡{nombre} está transmitiendo! Veremos cuántos kills hace hoy en cada game.",
    "¡Atención, todos! {nombre} empezó el game en vivo, ¿Quién trae las palomitas?",
    "¡{nombre} compartiendo pantalla! Momento de juzgar su habilidad.",
    "¡Ahora veremos si {nombre} es antiguo o nuevo!",
]

frases_fin_stream = [
    "{nombre} apagó el stream, ¿será que perdió la partida?",
    "Fin de la transmisión de {nombre}. ¿GG o FF?",
    "¡Listo! {nombre} dejó de compartir, todos a esperar el próximo en vivo.",
    "{nombre} terminó el streaming, que opinan juega o no juega.",
    "¡Se acabó el espectáculo! {nombre} cortó transmisión.",
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
        ]
    elif 12 <= hora < 19:
        saludos = [
            "Buenas tardes",
            "¡Excelente tarde!",
            "¡Feliz tarde!",
        ]
    else:
        saludos = [
            "Buenas noches",
            "¡Linda noche!",
            "¡Que descanses adiós!", 
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
    saludo = obtener_saludo_por_hora() 
    if veces == 1:
        frases += [
            f"¡Bienvenido, {nombre}! Es tu primera vez hoy. {saludo}.",
            f"Hola, {nombre}. Primera vez aquí. {saludo} y disfruta.",
            f"¡Encantado de verte por primera vez hoy, {nombre}! {saludo}.",
            f"¡Qué gusto recibirte, {nombre}! {saludo}.",
            f"¡Hola, {nombre}! Nos alegra mucho que estés aquí.",
            f"Un placer conocerte, {nombre}. Esperamos que la pases bien.",
            f"¡Es genial verte por aquí, {nombre}! Bienvenido.",
            f"{nombre}, eres muy bienvenido en este lugar.",
            f"{nombre}, gracias por unirte. Esperamos que disfrutes tu tiempo.",
            f"{nombre}, esta es tu primera visita hoy. ¡Disfrútala!",
            f"{nombre}, es un gusto saludarte por primera vez.",
            f"¡Nos alegra contar contigo, {nombre}!",
        ]
    elif veces == 2:
        frases += [
            f"{nombre}, qué bueno verte de nuevo. Segunda vez hoy.",
            f"{nombre}, parece que te gustó estar aquí. Segunda vez hoy.",
            f"¡Bienvenido otra vez, {nombre}! Nos alegra verte de vuelta.",
            f"¡Nos volvemos a encontrar, {nombre}! {saludo}.",
            f"{nombre}, ya viniste dos veces hoy. ¡Qué alegría!",
            f"Re bienvenido, {nombre}! Ya es tu segunda vez hoy.",
            f"{nombre}, siempre es bueno verte por aquí.",
            f"Nos alegra tu regreso, {nombre}.",
            f"{nombre}, segunda visita del día. ¡Gracias por volver!",
            f"{nombre}, bienvenido a este lugar.",
            f"{nombre}, parece que disfrutas tu tiempo aquí.",
            f"¡Qué gusto tenerte de nuevo, {nombre}!",
        ]      
    elif veces == 3:
        frases += [
            f"{nombre}! Bienvenido otra vez.",
            f"{nombre}, esta es tu tercera visita hoy. ¡Eres muy activo!",
            f"Wow, {nombre}! Tercera vez aquí hoy. ¡Impresionante!",
            f"{nombre}, ya te vi varias veces hoy. Tercera visita.",
            f"¡Tres veces en un día, {nombre}! Nos halaga tu presencia.",
            f"{nombre}, estás aprovechando al máximo tu día. {saludo}.",
            f"Tercera vez por aquí, {nombre}. ¡Eres de los nuestros!",
            f"{nombre}, bienvenido, eres parte importante aquí.",
            f"¡Tu presencia se nota, {nombre}!",
            f"{nombre}, qué bueno verte aquí.",
            f"{nombre}, tercer saludo del día para ti. ¡Bienvenido otra vez!",
            f"{nombre}, siempre es un placer saludarte.",
            f"¡Tres visitas, {nombre}! Qué entusiasmo.",
        ]
    else:
        frases += [
            f"{nombre}, ¿ya perdiste la cuenta? ¡{veces} veces hoy!",
            f"{nombre}, esta es tu visita número {veces} hoy. ¡Increíble!",
            f"{nombre}, parece que este canal es tu favorito. {veces} visitas hoy.",
            f"¡Qué alegría verte tantas veces, {nombre}!",
            f"{nombre}, gracias por visitarnos de nuevo.",
            f"{nombre}, tu energía es contagiosa. ¡Gracias por volver!",
            f"{nombre}, tu presencia siempre suma. {saludo}.",
            f"{nombre}, eres siempre bienvenido, no importa cuántas veces vengas.",
            f"{nombre}, se nota que te gusta estar aquí.",
            f"{nombre}, nos encanta verte tan seguido.",
            f"{nombre}, qué gusto que vengas tantas veces.",
            f"{nombre}, tu constancia se agradece mucho.",    
        ]
    frases += [
        f"{nombre}, qué alegría tenerte aquí. {saludo}.",
        f"{nombre}, me alegra mucho verte. {saludo}.",
        f"{nombre}, gracias por visitarnos hoy. ¡Bienvenido!",
        f"Siempre es un gusto saludarte, {nombre}.",
        f"{nombre}, que tengas un excelente día.",
        f"{nombre}, disfruta tu visita.",
        f"Esperamos que te sientas cómodo, {nombre}.",
        f"{nombre}, eres siempre bienvenido.",
        f"Nos alegra tu visita, {nombre}.",
        f"{nombre}, que tu tiempo aquí sea agradable.",
        f"Gracias por acompañarnos, {nombre}.",
        f"{nombre}, nos alegra que estés aquí.",
        f"Un placer verte por aquí, {nombre}.",
        f"¡{saludo}, {nombre}!",
        f"{nombre}, esta siempre será tu casa.",
        f"{nombre}, ojalá tengas una gran experiencia hoy.",
        f"Esperamos verte seguido por aquí, {nombre}.",
        f"Tu presencia nos alegra, {nombre}.",
        f"Bienvenido {nombre}, pásala genial.",
    ]
    return random.choice(frases)

def obtener_frase_despedida(nombre):
    saludo = obtener_saludo_por_hora()
    frases = [
        f"¡Nos vemos, {nombre}! Descansa. {saludo}.",
        f"¡Chau, {nombre}! {saludo} y pásala bien.",
        f"{nombre}, cuídate mucho. ¡Hasta la próxima! {saludo}.",
        f"¡{nombre}, vuelve pronto! {saludo}, me alegra verte siempre.",
        f"¡Hasta luego, {nombre}! {saludo} y éxitos en tu día.",
        f"¡Listo, {nombre}! {saludo}, hasta la próxima.",
        f"¡Espero verte de nuevo pronto, {nombre}! {saludo}.",
        f"¡No te olvides de nosotros, {nombre}! {saludo}.",
        f"¡Ve tranquilo, {nombre}! Aquí te esperamos. {saludo}.",
        f"¡Nos vemos en la próxima, {nombre}! {saludo}.",
        f"¡{nombre}, apaga la compu pero no la amistad. {saludo}.",
        f"¡Nos vemos en la próxima visita, {nombre}! {saludo}.",
        f"¡{nombre}, adiós, cuídate. {saludo}.",
        f"¡Hasta la vista, {nombre}! {saludo}.",
        f"¡Fue un gusto compartir contigo, {nombre}! {saludo}.",
        f"¡{nombre}, hasta el próximo saludo! {saludo}.",
        f"¡No es un adiós, es un hasta luego, {nombre}! {saludo}.",
        f"¡{nombre}, tu ausencia será notada. {saludo}.",
        f"¡Que descanses, {nombre}! {saludo}, recarga baterías.",
        f"¡{nombre}, nos vemos en la próxima visita! {saludo}.",
        f"Fue un placer compartir contigo, {nombre}.",
        f"Cuídate, {nombre}, y vuelve cuando quieras.",
        f"Gracias por tu compañía, {nombre}.",
        f"{nombre}, que todo te vaya muy bien.",
        f"{nombre}, aquí estaremos cuando regreses.",
        f"{nombre}, siempre es grato tenerte.",
        f"¡Hasta pronto, {nombre}!",
        f"{nombre}, que tengas un buen descanso.",
        f"Nos alegra haberte tenido aquí, {nombre}.",
        f"Que tengas un gran día, {nombre}.",
        f"¡Hasta la próxima, {nombre}!",
        f"{nombre}, gracias por compartir este momento.",
        f"{nombre}, fue un gusto verte.",
        f"Nos vemos pronto, {nombre}.",
        f"Siempre será un placer saludarte, {nombre}.",
        f"{nombre}, hasta la próxima oportunidad.",
        f"Que tengas una bonita jornada, {nombre}.",
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
    
    # === Evento de INICIO DE TRANSMISIÓN DE PANTALLA ===
    if after.channel and after.channel.id in CANALES_OBJETIVO_IDS:
        if not before.self_stream and after.self_stream:
           nombre_limpio = limpiar_nombre(member.display_name)
           texto = random.choice(frases_inicio_stream).format(nombre=nombre_limpio)
           voice_client = discord.utils.get(bot.voice_clients, guild=member.guild)
           if voice_client and voice_client.is_connected():
               await play_audio(voice_client, texto)

    # === Evento de FIN DE TRANSMISIÓN DE PANTALLA ===
    if before.channel and before.channel.id in CANALES_OBJETIVO_IDS:
        if before.self_stream and not after.self_stream:
            nombre_limpio = limpiar_nombre(member.display_name)
            texto = random.choice(frases_fin_stream).format(nombre=nombre_limpio)
            voice_client = discord.utils.get(bot.voice_clients, guild=member.guild)
            if voice_client and voice_client.is_connected():
                await play_audio(voice_client, texto)

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
