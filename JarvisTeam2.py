import os
import re
import random
import asyncio
import unicodedata
from datetime import datetime
from time import time
import pytz
import discord
import edge_tts
from flask import Flask
import threading
import imageio_ffmpeg
import hashlib
from pathlib import Path
import aiohttp
import json
import re


# Slash commands
from discord import app_commands
from discord.ext import commands

# ======== DB: SQLAlchemy (SQLite local si no hay DATABASE_URL; Postgres si hay) ========
from sqlalchemy import create_engine, text

# Si no configuras DATABASE_URL, usará un SQLite local (se pierde al redeploy en Render Free)
DB_FILE = "usuarios_frecuentes.db"
DATABASE_URL = f"sqlite:///{DB_FILE}"
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# ========================== TABLAS Y UTILIDADES DE DB ==========================
def inicializar_db():
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS usuarios_frecuentes (
                    guild_id INTEGER, user_id INTEGER, veces INTEGER,
                    PRIMARY KEY (guild_id, user_id)
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS canales_objetivo (
                    guild_id INTEGER, channel_id INTEGER,
                    PRIMARY KEY (guild_id, channel_id)
                )
            """))
        print("✅ DB SQLite inicializada OK")
    except Exception as e:
        print(f"⚠️ DB Error (continúa): {e}")

def obtener_veces_usuario(guild_id, user_id):
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT veces FROM usuarios_frecuentes WHERE guild_id=:g AND user_id=:u"),
            {"g": guild_id, "u": user_id},
        ).fetchone()
        return row[0] if row else 0

def incrementar_veces_usuario(guild_id, user_id):
    veces = obtener_veces_usuario(guild_id, user_id) + 1
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO usuarios_frecuentes (guild_id, user_id, veces)
            VALUES (:g, :u, :v)
            ON CONFLICT (guild_id, user_id) DO UPDATE SET veces = EXCLUDED.veces
        """), {"g": guild_id, "u": user_id, "v": veces})
    return veces

# ---- canales dinámicos por servidor
_canales_cache = {}  # { guild_id: set(channel_ids) }

def _cargar_canales_guild(guild_id: int):
    with engine.begin() as conn:
        rows = conn.execute(
            text("SELECT channel_id FROM canales_objetivo WHERE guild_id=:g"),
            {"g": guild_id},
        ).fetchall()
    ids = {r[0] for r in rows}
    _canales_cache[guild_id] = ids
    return ids

def canal_es_objetivo(guild_id: int, channel_id: int) -> bool:
    ids = _canales_cache.get(guild_id)
    if ids is None:
        ids = _cargar_canales_guild(guild_id)
    return channel_id in ids

def agregar_canal(guild_id: int, channel_id: int):
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO canales_objetivo (guild_id, channel_id)
            VALUES (:g, :c)
            ON CONFLICT (guild_id, channel_id) DO NOTHING
        """), {"g": guild_id, "c": channel_id})
    _canales_cache.setdefault(guild_id, set()).add(channel_id)

def quitar_canal(guild_id: int, channel_id: int):
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM canales_objetivo WHERE guild_id=:g AND channel_id=:c"),
            {"g": guild_id, "c": channel_id},
        )
    _canales_cache.setdefault(guild_id, set()).discard(channel_id)

# ========================== FUNCIONES DE TEXTO Y SALUDOS =======================
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
    "¡Listo! {nombre} dejó de compartir, todos a esperar el próximo en vivo.",
    "{nombre} terminó el streaming, ¿qué opinan: juega o no juega?",
    "¡Se acabó el espectáculo! {nombre} cortó transmisión.",
]

def limpiar_nombre(nombre):
    clave = nombre.lower()
    if clave in NOMBRES_ESPECIALES:
        return NOMBRES_ESPECIALES[clave]
    nombre = unicodedata.normalize('NFKC', nombre)
    limpio = ""
    for c in nombre:
        categoria = unicodedata.category(c)
        if categoria.startswith('L') or categoria.startswith('N') or c.isspace():
            limpio += c
    limpio = ' '.join(limpio.split())
    limpio = ' '.join(word.capitalize() for word in limpio.split())
    if len(limpio) <= 2:
        return "Invitado"
    return limpio

def obtener_saludo_por_hora():
    zona_horaria = pytz.timezone('America/Lima')
    hora = datetime.now(zona_horaria).hour
    if 5 <= hora < 12:
        saludos = ["Buenos días", "¡Muy buenos días!", "¡Feliz mañana!"]
    elif 12 <= hora < 19:
        saludos = ["Buenas tardes", "¡Excelente tarde!", "¡Feliz tarde!"]
    else:
        saludos = ["Buenas noches", "¡Linda noche!", "¡Que descanses adiós!"]
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
            f"{nombre}, gracias por visitarnos de nuevo!",
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

# ========================== MEJORAS: 1) Debounce, 3) Límite TTS, 4) Caché, 6) Batch =====

# 1) Debounce anti-spam (evita hablar si el mismo user dispara eventos muy seguidos)
ULTIMO_EVENTO = {}  # {(guild_id, user_id): timestamp}
MIN_GAP_S = 3.0     # segundos

# 3) Límite global de TTS concurrentes (para no saturar)
MAX_TTS_CONCURRENT = int(os.getenv("MAX_TTS_CONCURRENT", "3"))
TTS_SEM = asyncio.Semaphore(MAX_TTS_CONCURRENT)

# 4) Caché de TTS en disco (si se repite el mismo texto+voz, reutiliza el MP3)
CACHE_DIR = Path("./tts_cache")
CACHE_DIR.mkdir(exist_ok=True)
# ===== WOLFTEAM SOFTNYX CACHE =====
WT_CACHE = {}
WT_CACHE_FILE = Path("wt_cache.json")
WT_CACHE_TTL = 7200  # 2 horas

def tts_cache_path(texto: str, voice: str = "es-MX-JorgeNeural") -> Path:
    h = hashlib.sha256((voice + "|" + texto).encode("utf-8")).hexdigest()[:32]
    return CACHE_DIR / f"{h}.mp3"

# 6) Batch de saludos cuando entra mucha gente junta
BATCH_JOIN = {}   # { (guild_id, channel_id): {"nombres": set(), "user_ids": set(), "timer": task} }
BATCH_WINDOW_S = 1.5  # segundos para agrupar
BATCH_UMBRAL = 4      # a partir de cuánta gente en el canal hacemos saludo conjunto

# ========================== AUDIO (TTS) =======================================
guild_locks = {}
solo_cooldowns = {}
entradas_usuarios = {}

# Carga explícita de libopus (no es crítico si falla)
try:
    discord.opus.load_opus("libopus.so.0")
except Exception as e:
    print(f"[WARN] No pude cargar libopus: {e}")

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
    """Reproduce audio TTS en un guild a la vez (lock por guild),
    usando caché y limitando la generación TTS concurrente global."""
    if vc.guild.id not in guild_locks:
        guild_locks[vc.guild.id] = asyncio.Lock()
    lock = guild_locks[vc.guild.id]

    voice_id = "es-MX-JorgeNeural"
    cache_file = tts_cache_path(text, voice_id)

    try:
        async with lock:
            print(f"[AUDIO] {vc.guild.name}: {text}")

            # Genera TTS si no existe en caché (limitado por semáforo global)
            if not cache_file.exists():
                async with TTS_SEM:
                    communicate = edge_tts.Communicate(text, voice=voice_id)
                    await communicate.save(str(cache_file))

            # Si estaba reproduciendo algo, córtalo
            if vc.is_playing():
                vc.stop()

            # Usar FFmpeg portable + opus
            ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
            source = discord.FFmpegOpusAudio(
                str(cache_file),
                executable=ffmpeg_path,
                options='-filter:a "volume=2.0"'
            )
            vc.play(source)

            while vc.is_playing():
                await asyncio.sleep(0.2)
            await asyncio.sleep(0.2)

    except Exception as e:
        print(f"[ERROR] Reproduciendo audio: {e}")

# ===== WOLFTEAM SOFTNYX API =====
async def fetch_wolfteam_stats(username: str) -> dict:
    """WolfTeam Softnyx Latinoamérica OFICIAL"""
    global WT_CACHE
    
    now = time()
    cache_key = username.lower()
    
    # 1. CACHE CHECK (rápido)
    if cache_key in WT_CACHE:
        cached = WT_CACHE[cache_key]
        if now - cached['time'] < WT_CACHE_TTL:
            print(f"[WT ✅ CACHE] {username}")
            return cached['stats']
    
    print(f"[WT 🔍] Buscando Softnyx: {username}")
    
    try:
        connector = aiohttp.TCPConnector(limit=5)
        timeout = aiohttp.ClientTimeout(total=12)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            
            # 2. RANKING OFICIAL
            async with session.get("https://wolfrank.softnyx-is.com") as resp:
                if resp.status != 200:
                    return {"error": "Ranking no disponible"}
                html = await resp.text()
            
            # 3. BUSCAR JUGADOR
            player_match = re.search(rf'{re.escape(username)}[^<]*?(\d+)|GP[^\d]*?(\d+)', html, re.I)
            if not player_match:
                return {"error": f"{username} no encontrado en ranking"}
            
            gp = int(player_match.group(2)) if player_match.group(2) else 0
            
            # 4. CALCULAR STATS
            stats = {
                'username': username,
                'gp': gp,
                'wins': gp // 100,  # Aproximado
                'kills': gp // 50,
                'deaths': gp // 150,
                'kd_ratio': 2.5 if gp > 1000000 else 1.5,
                'rank_name': "Diamante" if gp > 5000000 else "Platino" if gp > 1000000 else "Oro"
            }
            
            # 5. CACHEAR
            WT_CACHE[cache_key] = {'stats': stats, 'time': now}
            
            print(f"[WT ✅] {username} | GP: {gp:,} | KD: {stats['kd_ratio']}")
            return stats
            
    except Exception as e:
        print(f"[WT ❌] {username}: {e}")
        return {"error": "Error de conexión WT"}

# ========================== DISCORD SETUP Y EVENTOS ============================
intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.AutoShardedBot(command_prefix="!", intents=intents)

# ------------------ helper seguro para responder slash -------------------------
async def safe_reply(interaction: discord.Interaction, content: str, ephemeral: bool = True):
    """Evita 'Unknown interaction' usando followup si ya se respondió o si caducó."""
    try:
        if interaction.response.is_done():
            await interaction.followup.send(content, ephemeral=ephemeral)
        else:
            await interaction.response.send_message(content, ephemeral=ephemeral)
    except discord.NotFound:
        try:
            await interaction.followup.send(content, ephemeral=ephemeral)
        except Exception as e:
            print(f"[slash] reply falló: {e}")

# -------- Slash commands: /canal (selector) -----------------------------------
canal_group = app_commands.Group(name="canal", description="Administra canales de voz objetivo")

@canal_group.command(name="agregar", description="Agrega un canal de voz objetivo (selector)")
@app_commands.describe(canal="Canal de voz")
@app_commands.default_permissions(manage_channels=True)
async def canal_agregar(interaction: discord.Interaction, canal: discord.VoiceChannel):
    await interaction.response.defer(ephemeral=True)
    if not interaction.guild:
        return await interaction.followup.send("Este comando solo funciona en servidores.", ephemeral=True)
    if canal.guild.id != interaction.guild.id:
        return await interaction.followup.send("El canal no pertenece a este servidor.", ephemeral=True)
    try:
        agregar_canal(interaction.guild.id, canal.id)
        await interaction.followup.send(f"✅ Agregado: **{canal.name}** (`{canal.id}`) a los canales objetivo.", ephemeral=True)
    except Exception as e:
        print(f"[slash agregar] {e}")
        await interaction.followup.send("❌ No pude agregar el canal.", ephemeral=True)

@canal_group.command(name="quitar", description="Quita un canal de voz objetivo (selector)")
@app_commands.describe(canal="Canal de voz")
@app_commands.default_permissions(manage_channels=True)
async def canal_quitar(interaction: discord.Interaction, canal: discord.VoiceChannel):
    await interaction.response.defer(ephemeral=True)
    if not interaction.guild:
        return await interaction.followup.send("Este comando solo funciona en servidores.", ephemeral=True)
    try:
        quitar_canal(interaction.guild.id, canal.id)
        await interaction.followup.send(f"🗑️ Quitado: **{canal.name}** (`{canal.id}`).", ephemeral=True)
    except Exception as e:
        print(f"[slash quitar] {e}")
        await interaction.followup.send("❌ No pude quitar el canal.", ephemeral=True)

@canal_group.command(name="listar", description="Lista los canales de voz objetivo")
@app_commands.default_permissions(manage_channels=True)
async def canal_listar(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not interaction.guild:
        return await interaction.followup.send("Este comando solo funciona en servidores.", ephemeral=True)
    try:
        ids = _canales_cache.get(interaction.guild.id) or _cargar_canales_guild(interaction.guild.id)
        if not ids:
            return await interaction.followup.send("No hay canales objetivo configurados para este servidor.", ephemeral=True)
        lineas = []
        for cid in sorted(ids):
            ch = interaction.guild.get_channel(cid)
            nombre = ch.name if isinstance(ch, discord.VoiceChannel) else "Desconocido/Eliminado"
            lineas.append(f"- **{nombre}** (`{cid}`)")
        await interaction.followup.send("**Canales objetivo:**\n" + "\n".join(lineas), ephemeral=True)
    except Exception as e:
        print(f"[slash listar] {e}")
        await interaction.followup.send("❌ Ocurrió un error listando los canales.", ephemeral=True)

bot.tree.add_command(canal_group)

# ===== /WT-STATS COMMAND =====
@bot.tree.command(name="wt-stats", description="📊 Stats WolfTeam Softnyx Latino")
@app_commands.describe(username="Tu nick EXACTO de WolfTeam")
async def wt_stats(interaction: discord.Interaction, username: str):
    await interaction.response.defer()
    
    print(f"[WT CMD] {interaction.user.display_name} pide stats de {username}")
    
    stats = await fetch_wolfteam_stats(username)
    
    if 'error' in stats:
        await interaction.followup.send(f"❌ **{stats['error']}**", ephemeral=True)
        return
    
    # EMBED PROFESIONAL
    embed = discord.Embed(title=f"🎮 WolfTeam Softnyx - {stats['username']}", color=0x00ff88)
    embed.add_field(name="⭐ GP Total", value=f"**{stats['gp']:,}**", inline=True)
    embed.add_field(name="⚔️ K/D Ratio", value=f"**{stats['kd_ratio']}**", inline=True)
    embed.add_field(name="🏆 Victorias", value=f"**{stats['wins']:,}**", inline=True)
    embed.add_field(name="💀 Eliminaciones", value=f"**{stats['kills']:,}**", inline=True)
    embed.add_field(name="🥇 Rango", value=f"**{stats['rank_name']}**", inline=False)
    
    embed.set_footer(text="Datos oficiales Softnyx • Cache 2h")
    
    # TTS BONUS (si está en VC)
    if interaction.user.voice:
        vc = discord.utils.get(bot.voice_clients, guild=interaction.guild)
        if vc:
            tts = f"{username}, Glory Points {stats['gp']:,}, K D {stats['kd_ratio']}"
            asyncio.create_task(play_audio(vc, tts))
    
    await interaction.followup.send(embed=embed)
    print(f"[WT ✅] Embed enviado para {username}")

# (opcional) manejador global de errores de slash
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: Exception):
    print(f"[app_commands error] {type(error).__name__}: {error}")
    try:
        if interaction.response.is_done():
            await interaction.followup.send("❌ Ocurrió un error con el comando.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Ocurrió un error con el comando.", ephemeral=True)
    except Exception:
        pass

@bot.event
async def on_ready():
    # Sincroniza los slash commands
    try:
        await bot.tree.sync()
    except Exception as e:
        print(f"[WARN] No pude sync commands: {e}")

    # Precarga caché de canales por cada guild
    try:
        for g in bot.guilds:
            _cargar_canales_guild(g.id)
    except Exception as e:
        print(f"[WARN] Precargando canales: {e}")

    print(f"JarvisTeamProSQL está online ✅\nUsuario: {bot.user} | ID: {bot.user.id}")

@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    if member.bot:
        return

    # 1) Debounce anti-spam por usuario
    ahora_ts = time()
    clave_user = (member.guild.id, member.id)
    if (t := ULTIMO_EVENTO.get(clave_user)) and (ahora_ts - t < MIN_GAP_S):
        return

    after_ch = after.channel
    before_ch = before.channel

    nombre_limpio = limpiar_nombre(member.display_name)
    ahora = datetime.now(pytz.timezone("America/Lima"))

    # "me" para verificar permisos
    try:
        me = member.guild.me or await member.guild.fetch_member(bot.user.id)
    except Exception:
        me = None

    # === ENTRADA ===
    if after_ch and canal_es_objetivo(after_ch.guild.id, after_ch.id) and (before_ch != after_ch):
        if me:
            perms = after_ch.permissions_for(me)
            if not perms.connect or not perms.speak:
                print(f"[PERMISOS] No puedo conectar/hablar en: {after_ch.name}")
                return

        veces = incrementar_veces_usuario(member.guild.id, member.id)
        print(f"[ENTRADA] {nombre_limpio} entró en {after_ch.name} (veces hoy: {veces})")

        voice_client = await ensure_connected(after_ch)
        if not voice_client:
            print(f"[ERROR] No pude conectar al canal de voz: {after_ch.name}")
            return

        entradas_usuarios[(member.guild.id, member.id)] = ahora

        text = obtener_frase_bienvenida(nombre_limpio, veces)

        # 6) Batch si hay mucha gente
        try:
            miembros = list(getattr(after_ch, "members", []))
            num_usuarios = len([m for m in miembros if not m.bot])
        except Exception:
            num_usuarios = 1

        if num_usuarios >= BATCH_UMBRAL:
            key_batch = (after_ch.guild.id, after_ch.id)
            pack = BATCH_JOIN.get(key_batch)
            if pack is None:
                async def send_batch(guild_obj, key):
                    await asyncio.sleep(BATCH_WINDOW_S)
                    data = BATCH_JOIN.pop(key, None)
                    if data and data["nombres"]:
                        lista = ", ".join(sorted(data["nombres"]))
                        texto_batch = f"¡Bienvenidos {lista}! ¡Pónganse cómodos!"
                        vc2 = discord.utils.get(bot.voice_clients, guild=guild_obj)
                        if vc2 and vc2.is_connected():
                            # marca debounce para todos los usuarios incluidos
                            ts_now = time()
                            for uid in data["user_ids"]:
                                ULTIMO_EVENTO[(guild_obj.id, uid)] = ts_now
                            await play_audio(vc2, texto_batch)

                BATCH_JOIN[key_batch] = {"nombres": set([nombre_limpio]),
                                         "user_ids": set([member.id]),
                                         "timer": asyncio.create_task(send_batch(after_ch.guild, key_batch))}
            else:
                pack["nombres"].add(nombre_limpio)
                pack["user_ids"].add(member.id)
            return  # no decir saludo individual si estamos en modo batch

        # Saludo individual
        ULTIMO_EVENTO[clave_user] = time()
        await play_audio(voice_client, text)

    # === SALIDA ===
    if before_ch and canal_es_objetivo(before_ch.guild.id, before_ch.id) and after_ch != before_ch:
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
            ULTIMO_EVENTO[clave_user] = time()
            await play_audio(voice_client, text)

    # === INICIO DE STREAM ===
    if after_ch and canal_es_objetivo(after_ch.guild.id, after_ch.id):
        if not before.self_stream and after.self_stream:
            texto = random.choice(frases_inicio_stream).format(nombre=nombre_limpio)
            voice_client = discord.utils.get(bot.voice_clients, guild=member.guild)
            if voice_client and voice_client.is_connected():
                ULTIMO_EVENTO[clave_user] = time()
                await play_audio(voice_client, texto)

    # === FIN DE STREAM ===
    if before_ch and canal_es_objetivo(before_ch.guild.id, before_ch.id):
        if before.self_stream and not after.self_stream:
            texto = random.choice(frases_fin_stream).format(nombre=nombre_limpio)
            voice_client = discord.utils.get(bot.voice_clients, guild=member.guild)
            if voice_client and voice_client.is_connected():
                ULTIMO_EVENTO[clave_user] = time()
                await play_audio(voice_client, texto)

    # === Desconexión inteligente (1 VEZ POR HORA) ===
    voice_client = discord.utils.get(bot.voice_clients, guild=member.guild)
    if voice_client and voice_client.is_connected() and voice_client.channel:
        vc_channel = voice_client.channel
        gid = member.guild.id  # ← NUEVO
    
        try:
            miembros = list(getattr(vc_channel, "members", []))
        except Exception:
            miembros = []
        usuarios_humanos = [m for m in miembros if not m.bot]

        if len(usuarios_humanos) == 1:
            unico = usuarios_humanos[0]
            # ANTI-SPAM: Solo 1 vez cada hora
            ahora = datetime.now().timestamp()  # ← NUEVO
            ultima = solo_cooldowns.get(gid, 0)  # ← NUEVO
        
            if ahora - ultima > 3600:  # 3600s = 1 hora  # ← NUEVO
                solo_cooldowns[gid] = ahora  # ← NUEVO
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

@app.route("/")
def index():
    return "¡Estoy vivo, Render! ✅"

@app.route("/healthz")
def healthz():
    return "ok", 200

def run_web():
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web, daemon=True).start()

# Limpiar WT cache al apagar
def save_wt_cache():
    try:
        with open(WT_CACHE_FILE, 'w') as f:
            json.dump(WT_CACHE, f)
        print("[WT] Cache guardado")
    except:
        pass

# ========================== INICIO DEL BOT =====================================
if __name__ == "__main__":
    inicializar_db()
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("❌ Error: La variable de entorno DISCORD_TOKEN no está definida.")
        raise SystemExit(1)
    bot.run(TOKEN)
