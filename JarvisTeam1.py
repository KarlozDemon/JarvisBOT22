import discord
import edge_tts
import asyncio
import os
import re
import unicodedata
import random
import pytz
from flask import Flask
import threading
from datetime import datetime
import json
from pathlib import Path

# ========================== CONFIGURACIÓN GENERAL ==============================
CANALES_OBJETIVO_IDS = [
    1383150389037367487, # Pride Battle - Clan1 Voz
    1375567307782357047, # PiscoSour™ - Team1 Voz
    1289380412434681879, # NyxLeyendasWT - CopaSoftnyx
]

datos_db = {}
db_lock = threading.Lock()

# ========================== UTILIDADES Y DATOS PERSISTENTES ====================

def inicializar_db():
    """Sistema JSON - Sin Database"""
    global datos_db
    archivo_db = Path("usuarios_frecuentes.json")
    
    try:
        if archivo_db.exists():
            with open(archivo_db, 'r', encoding='utf-8') as f:
                datos_db = json.load(f)
            print("✅ JSON cargado correctamente")
        else:
            datos_db = {}  # { "guild123": { "user456": 5 } }
            print("📝 JSON creado nuevo")
    except Exception as e:
        print(f"⚠️ Error JSON: {e}")
        datos_db = {}

def obtener_veces_usuario(guild_id, user_id):
    global datos_db
    with db_lock:
        guild_data = datos_db.get(str(guild_id), {})
        return guild_data.get(str(user_id), 0)

def incrementar_veces_usuario(guild_id, user_id):
    global datos_db
    with db_lock:
        guild_str = str(guild_id)
        user_str = str(user_id)
        
        if guild_str not in datos_db:
            datos_db[guild_str] = {}
        if user_str not in datos_db[guild_str]:
            datos_db[guild_str][user_str] = 0
            
        datos_db[guild_str][user_str] += 1
        veces = datos_db[guild_str][user_str]
        
        # Guardar cada 10 cambios
        if veces % 10 == 0:
            pass
            
        return veces

# ========================== FUNCIONES DE TEXTO Y SALUDOS =======================

# CAMBIO: llaves en minúsculas para que el .lower() matchee
NOMBRES_ESPECIALES = {
    "josé is back": "José",
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
    "¡Listo! {nombre} dejo de compartir, todos a esperar el próximo en vivo.",
    "{nombre} terminó el streaming, que opinan juega o no juega.",
    "¡Se acabó el espectáculo! {nombre} corto trasmisión.",
]
 
def limpiar_nombre(nombre):
    # CAMBIO: usar clave en lower para casos especiales
    clave = nombre.lower()
    if clave in NOMBRES_ESPECIALES:
        return NOMBRES_ESPECIALES[clave]

    # Paso 1: Normaliza el nombre a NFKC
    nombre = unicodedata.normalize('NFKC', nombre)

    # Paso 2: Elimina símbolos, emojis y puntuación, deja solo letras y números
    limpio = ""
    for c in nombre:
        categoria = unicodedata.category(c)
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

# NUEVO: carga explícita de libopus para evitar errores en algunos entornos
try:
    discord.opus.load_opus("libopus.so.0")
except Exception as e:
    print(f"[WARN] No pude cargar libopus: {e}")

# NUEVO: lock por GUILD + helper de conexión robusta
guild_connect_locks = {}

async def ensure_connected(target_channel: discord.VoiceChannel):
    gid = target_channel.guild.id
    if gid not in guild_connect_locks:
        guild_connect_locks[gid] = asyncio.Lock()
    async with guild_connect_locks[gid]:
        vc = discord.utils.get(bot.voice_clients, guild=target_channel.guild)
        if vc and vc.is_connected():
            if vc.channel and vc.channel.id == target_channel.id:
                return vc
            try:
                await vc.move_to(target_channel)
                return vc
            except Exception as e:
                print(f"[WARN] move_to falló: {e}; desconecto y reintento")
                try:
                    await vc.disconnect(force=True)
                except Exception as e2:
                    print(f"[WARN] disconnect falló: {e2}")
        try:
            vc = await target_channel.connect(reconnect=True, timeout=10)
            return vc
        except Exception as e:
            print(f"[ERROR] connect falló: {e}. Reintento una vez…")
            try:
                tmp = discord.utils.get(bot.voice_clients, guild=target_channel.guild)
                if tmp:
                    await tmp.disconnect(force=True)
            except Exception:
                pass
            try:
                vc = await target_channel.connect(reconnect=True, timeout=10)
                return vc
            except Exception as e2:
                print(f"[ERROR] segundo connect falló: {e2}")
                return None

async def play_audio(vc, text):
    if vc.guild.id not in guild_locks:
        guild_locks[vc.guild.id] = asyncio.Lock()
    lock = guild_locks[vc.guild.id]
    filename = f"tts_{vc.guild.id}.mp3"
    try:
        async with lock:
            print(f"[AUDIO] {vc.guild.name}: {text}")
            # CAMBIO: cortar audio previo para evitar procesos ffmpeg zombis
            if vc.is_playing():
                vc.stop()

            communicate = edge_tts.Communicate(text, voice="es-ES-ElviraNeural")
            await communicate.save(filename)
            vc.play(discord.FFmpegPCMAudio(filename, executable="ffmpeg", options='-filter:a "volume=2.0"'))
            # CAMBIO: espera en intervalos cortos
            while vc.is_playing():
                await asyncio.sleep(0.2)
            await asyncio.sleep(0.2)
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

# CAMBIO: handler reescrito con snapshots, validaciones y ensure_connected

def guardar_datos():
    """Guardar JSON automáticamente"""
    global datos_db
    try:
        with open("usuarios_frecuentes.json", 'w', encoding='utf-8') as f:
            json.dump(datos_db, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[ERROR] Guardando JSON: {e}")

@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return

    # Snapshots de canales (evita carreras)
    after_ch = after.channel
    before_ch = before.channel

    nombre_limpio = limpiar_nombre(member.display_name)
    ahora = datetime.now(pytz.timezone("America/Lima"))

    # "me" seguro para permisos
    try:
        me = member.guild.me or await member.guild.fetch_member(bot.user.id)
    except Exception:
        me = None

    # === Evento de ENTRADA ===
    if after_ch and after_ch.id in CANALES_OBJETIVO_IDS and (before_ch != after_ch):
        if me:
            perms = after_ch.permissions_for(me)
            if not perms.connect or not perms.speak:
                print(f"[PERMISOS] No puedo conectar/hablar en: {after_ch.name}")
                return

        # DB
        veces = incrementar_veces_usuario(member.guild.id, member.id)
        print(f"[ENTRADA] {nombre_limpio} entró en {after_ch.name} (veces hoy: {veces})")

        # Conexión/movimiento serializado por guild
        voice_client = await ensure_connected(after_ch)
        if not voice_client:
            print(f"[ERROR] No pude conectar al canal de voz: {after_ch.name}")
            return

        entradas_usuarios[(member.guild.id, member.id)] = ahora

        text = obtener_frase_bienvenida(nombre_limpio, veces)

        # Conteo de miembros con protección
        try:
            miembros = list(getattr(after_ch, "members", []))
            num_usuarios = len([m for m in miembros if not m.bot])
            if num_usuarios >= 20:
                text = f"¡Wow, esto se está llenando! Bienvenido {nombre_limpio}, y saludos a todos los presentes."
        except Exception:
            pass

        await play_audio(voice_client, text)

    # === Evento de SALIDA ===
    if before_ch and before_ch.id in CANALES_OBJETIVO_IDS and after_ch != before_ch:
        print(f"[SALIDA] {nombre_limpio} salió de {before_ch.name}")

        voice_client = discord.utils.get(bot.voice_clients, guild=member.guild)
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

    # === INICIO DE TRANSMISIÓN DE PANTALLA ===
    if after_ch and after_ch.id in CANALES_OBJETIVO_IDS:
        if not before.self_stream and after.self_stream:
            texto = random.choice(frases_inicio_stream).format(nombre=nombre_limpio)
            voice_client = discord.utils.get(bot.voice_clients, guild=member.guild)
            if voice_client and voice_client.is_connected():
                await play_audio(voice_client, texto)
            # Si quieres hablar aunque no esté conectado, podrías:
            # else:
            #     vc = await ensure_connected(after_ch)
            #     if vc:
            #         await play_audio(vc, texto)

    # === FIN DE TRANSMISIÓN DE PANTALLA ===
    if before_ch and before_ch.id in CANALES_OBJETIVO_IDS:
        if before.self_stream and not after.self_stream:
            texto = random.choice(frases_fin_stream).format(nombre=nombre_limpio)
            voice_client = discord.utils.get(bot.voice_clients, guild=member.guild)
            if voice_client and voice_client.is_connected():
                await play_audio(voice_client, texto)

    # === Desconexión inteligente ===
    voice_client = discord.utils.get(bot.voice_clients, guild=member.guild)
    if voice_client and voice_client.is_connected() and voice_client.channel:
        vc_channel = voice_client.channel
        try:
            miembros = list(getattr(vc_channel, "members", []))
        except Exception:
            miembros = []
        usuarios_humanos = [m for m in miembros if not m.bot]

        if len(usuarios_humanos) == 1:
            unico = usuarios_humanos[0]
            text = f"{unico.display_name}, parece que ahora estás solo. ¡Aquí sigo contigo!"
            await play_audio(voice_client, text)
        elif not usuarios_humanos:
            text = "Parece que me quedé solito aquí…"
            await play_audio(voice_client, text)
            try:
                if voice_client.is_playing():
                    voice_client.stop()
            except Exception:
                pass
            await voice_client.disconnect()

# ========================== SERVIDOR FLASK KEEP-ALIVE ==========================
app = Flask(__name__)

@app.route('/')
def index():
    return "¡Estoy vivo, Render! ✅"

def run_web():
    # CAMBIO: usar PORT de entorno si existe (Render Web Service)
    port = int(os.environ.get("PORT", "10000"))
    app.run(host='0.0.0.0', port=port)  # CAMBIO

threading.Thread(target=run_web, daemon=True).start()

# ========================== INICIO DEL BOT =====================================

# Guardar al apagar
import atexit
atexit.register(guardar_datos)

print("🚀 Bot listo para iniciar")

if __name__ == "__main__":
    inicializar_db()
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("❌ Error: La variable de entorno DISCORD_TOKEN no está definida.")
        exit(1)
    bot.run(TOKEN)
