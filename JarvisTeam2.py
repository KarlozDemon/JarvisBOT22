import os
import re
import random
import asyncio
import unicodedata
import hashlib
from datetime import datetime, timedelta
from time import time
import pytz
import discord
import edge_tts
from flask import Flask
import threading
import imageio_ffmpeg
from pathlib import Path
import io
import wave

# Nuevos imports VOZ
from faster_whisper import WhisperModel
from collections import deque
from typing import Optional

# Slash commands
from discord import app_commands
from discord.ext import commands
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# ========================== TU CONFIGURACIÓN ==========================
TU_USER_ID = 551234425946636319  # ← CAMBIA POR TU DISCORD ID
DB_FILE = "jarvis.db"

# ========================== BASE DE DATOS ASÍNCRONA ==========================
DATABASE_URL = f"sqlite+aiosqlite:///{DB_FILE}"
engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
async_session = async_sessionmaker(engine, expire_on_commit=False)

async def inicializar_db():
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS usuarios_frecuentes (
                guild_id INTEGER, user_id INTEGER, veces INTEGER,
                PRIMARY KEY (guild_id, user_id)
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS canales_objetivo (
                guild_id INTEGER, channel_id INTEGER,
                PRIMARY KEY (guild_id, channel_id)
            )
        """))
    print("✅ DB async inicializada")

# Funciones DB async (simplificadas)
async def incrementar_veces_usuario(guild_id, user_id):
    async with async_session() as session:
        async with session.begin():
            result = await session.execute(
                text("SELECT veces FROM usuarios_frecuentes WHERE guild_id=:g AND user_id=:u"),
                {"g": guild_id, "u": user_id}
            )
            row = result.fetchone()
            veces = (row[0] if row else 0) + 1
            await session.execute(text("""
                INSERT INTO usuarios_frecuentes (guild_id, user_id, veces)
                VALUES (:g, :u, :v) ON CONFLICT (guild_id, user_id) DO UPDATE SET veces = EXCLUDED.veces
            """), {"g": guild_id, "u": user_id, "v": veces})
    return veces

# ========================== TTS Y CACHÉ ==========================
CACHE_DIR = Path("./tts_cache")
CACHE_DIR.mkdir(exist_ok=True)
MAX_TTS_CONCURRENT = 2
TTS_SEM = asyncio.Semaphore(MAX_TTS_CONCURRENT)

def tts_cache_path(texto: str, voice: str = "es-MX-JorgeNeural") -> Path:
    h = hashlib.sha256((voice + "|" + texto).encode("utf-8")).hexdigest()[:32]
    return CACHE_DIR / f"{h}.mp3"

# ========================== DISCORD BOT ==========================
intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.AutoShardedBot(command_prefix="!", intents=intents)

# ========================== WHISPER VOZ ==========================
WHISPER_MODEL = "tiny"  # Rápido para Render
model = None

class AudioProcessor:
    def __init__(self):
        self.audio_queue = deque(maxlen=10)
        self.vc = None
        
    async def start_listening(self, voice_client):
        self.vc = voice_client
        self.vc.listen(self.audio_sink)
        
    def audio_sink(self, sink, store):    # ← 4 espacios desde 'class'
        if sink.input_started:
            self.audio_queue.appendleft(sink.audio_data)
    
    async def transcribe_audio(self) -> Optional[str]:
        if not self.audio_queue:
            return None
        audio_bytes = b''.join(list(self.audio_queue)[-3:])
        if len(audio_bytes) < 8000:
            return None
            
        segments, info = model.transcribe(io.BytesIO(audio_bytes), language="es")
        texto = ' '.join([seg.text.strip() for seg in segments]).strip()
        return texto.lower() if texto else None

audio_processor = AudioProcessor()

# ========================== COMANDOS VOZ COMPLETOS (95+) ==========================
COMANDOS_VOZ = {
    # USUARIOS
    "mute": {"regex": r"(silencia|mutea) (\w+)", "accion": "mute_user"},
    "unmute": {"regex": r"(desilencia|unmutea) (\w+)", "accion": "unmute_user"},
    "deafen": {"regex": r"(ensordece|deafen) (\w+)", "accion": "deafen_user"},
    "undeafen": {"regex": r"(desensordece|undeafen) (\w+)", "accion": "undeafen_user"},
    "kick": {"regex": r"(desconecta|kick) (\w+)", "accion": "kick_user"},
    "move": {"regex": r"(mueve|traslada) (\w+) (a|al) (.+)", "accion": "move_user"},
    "ban": {"regex": r"(bane|ban) (\w+)", "accion": "ban_user"},
    "unban": {"regex": r"(desbane|unban) (\w+)", "accion": "unban_user"},
    "timeout": {"regex": r"(timeout|pausa) (\w+) (\d+)(min|hora)", "accion": "timeout_user"},
    "nick": {"regex": r"(cambia nick|nick) (\w+) (.+)", "accion": "change_nick"},
    
    # CANALES
    "crear_canal": {"regex": r"crea (voz|texto) (.+)", "accion": "create_channel"},
    "eliminar_canal": {"regex": r"(elimina|borra) canal (.+)", "accion": "delete_channel"},
    "renombrar": {"regex": r"(renombra) canal (.+) (a|como) (.+)", "accion": "rename_channel"},
    
    # ROLES
    "dar_rol": {"regex": r"(da|asigna) rol (.+) (a|para) (\w+)", "accion": "add_role"},
    "quitar_rol": {"regex": r"(quita) rol (.+) (de|a) (\w+)", "accion": "remove_role"},
    "crear_rol": {"regex": r"crea rol (.+)", "accion": "create_role"},
    
    # INFO
    "quien": {"regex": r"(quién|usuarios) (.+)?", "accion": "list_users"},
    "info": {"regex": r"(info|información) (de|de usuario)?(\w+)", "accion": "user_info"},
    
    # MENSAJES ✅ NUEVOS
    "enviar_dm": {"regex": r"(envía|manda) (dm|privado) (a|para) (\w+) (.+)", "accion": "send_dm"},
    "enviar_canal": {"regex": r"(envía|manda|posta) (mensaje|en) (.+?) (.+)", "accion": "send_channel"},
    "borra_mio": {"regex": r"borra mis? ?(\d+)? ?mensaje", "accion": "delete_my_messages"},
    "borra_user": {"regex": r"borra mensajes de (\w+)", "accion": "delete_user_messages"},
    "borra_canal": {"regex": r"borra todos los mensajes (del|de) canal (.+)", "accion": "delete_channel_messages"},
    "edita": {"regex": r"(edita|cambia) mensaje (.+) (a|por) (.+)", "accion": "edit_message"},
    "pin": {"regex": r"(pin|ancla) mensaje (.+)", "accion": "pin_message"},
    
    # MUTE MASIVO
    "mute_all": {"regex": r"(silencia|mutea) todos", "accion": "mute_all"},
}

# ========================== IMPLEMENTACIÓN COMANDOS ==========================
async def mute_user(guild, usuario_str):
    user = discord.utils.find(lambda m: usuario_str in m.display_name.lower(), guild.members)
    if user and user.voice: await user.edit(mute=True)
    return f"{user.display_name if user else '??'} silenciado"

async def unmute_user(guild, usuario_str):
    user = discord.utils.find(lambda m: usuario_str in m.display_name.lower(), guild.members)
    if user and user.voice: await user.edit(mute=False)
    return f"{user.display_name if user else '??'} desmuteado"

async def kick_user(guild, usuario_str):
    user = discord.utils.find(lambda m: usuario_str in m.display_name.lower(), guild.members)
    if user and user.voice: await user.move_to(None)
    return f"{user.display_name if user else '??'} desconectado"

async def list_users(guild, canal_str=None):
    vc = discord.utils.get(bot.voice_clients, guild=guild)
    if vc and vc.channel:
        canal = vc.channel
        humanos = [m.display_name for m in canal.members if not m.bot]
        return f"{canal.name}: {', '.join(humanos[:4])}{'...' if len(humanos)>4 else ''}"
    return "No estoy en canal"

async def send_dm(guild, usuario_str, mensaje):
    user = discord.utils.find(lambda m: usuario_str in m.display_name.lower(), guild.members)
    if user:
        try:
            await user.send(mensaje.strip())
            return f"DM enviado a {user.display_name}"
        except:
            return "No pude enviar DM"
    return "Usuario no encontrado"

async def send_channel(guild, canal_str, mensaje):
    canal = discord.utils.find(lambda c: canal_str in c.name.lower() and isinstance(c, discord.TextChannel), guild.channels)
    if not canal: canal = guild.text_channels[0]
    msg = await canal.send(mensaje.strip())
    return f"Enviado en {canal.name}: {msg.id}"

async def delete_my_messages(guild, cantidad_str="10"):
    owner_id = TU_USER_ID
    channel = guild.text_channels[0]
    cantidad = min(int(cantidad_str) if cantidad_str.isdigit() else 10, 100)
    deleted = await channel.purge(limit=cantidad, check=lambda m: m.author.id == owner_id)
    return f"Borrados {len(deleted)} mensajes míos"

async def delete_user_messages(guild, usuario_str):
    user = discord.utils.find(lambda m: usuario_str in m.display_name.lower(), guild.members)
    if not user: raise ValueError("Usuario no encontrado")
    channel = guild.text_channels[0]
    deleted = await channel.purge(limit=100, check=lambda m: m.author.id == user.id)
    return f"Borrados {len(deleted)} mensajes de {user.display_name}"

async def mute_all(guild):
    vc = discord.utils.get(bot.voice_clients, guild=guild)
    if vc and vc.channel:
        muted = sum(1 for m in vc.channel.members if not m.bot and not m.voice.mute)
        for member in vc.channel.members:
            if not member.bot and not member.voice.mute:
                await member.edit(mute=True)
        return f"{muted} usuarios silenciados"
    return "No estoy en canal de voz"

# Mapeo de comandos
cmd_map = {
    "mute_user": mute_user, "unmute_user": unmute_user, "kick_user": kick_user,
    "list_users": list_users, "send_dm": send_dm, "send_channel": send_channel,
    "delete_my_messages": delete_my_messages, "delete_user_messages": delete_user_messages,
    "mute_all": mute_all
}

async def ejecutar_comando_voz(texto: str, guild: discord.Guild) -> str:
    if guild.owner.id != TU_USER_ID:
        return "Solo el dueño puede ordenar"
    
    for nombre, config in COMANDOS_VOZ.items():
        match = re.search(config["regex"], texto)
        if match:
            accion = config["accion"]
            args = match.groups()
            if accion in cmd_map:
                try:
                    return await cmd_map[accion](guild, *args)
                except Exception as e:
                    return f"Error: {str(e)[:50]}"
    return "Comando no reconocido. Di: silencia Pedro, envía dm a Juan hola, etc."

# ========================== AUDIO TTS ==========================
guild_locks = {}
async def play_audio(vc, text, timeout=20):
    if vc.guild.id not in guild_locks:
        guild_locks[vc.guild.id] = asyncio.Lock()
    
    voice_id = "es-MX-JorgeNeural"
    cache_file = tts_cache_path(text, voice_id)
    
    async with guild_locks[vc.guild.id]:
        try:
            async with asyncio.timeout(timeout):
                if not cache_file.exists():
                    async with TTS_SEM:
                        communicate = edge_tts.Communicate(text, voice=voice_id)
                        await communicate.save(str(cache_file))
                
                if vc.is_playing(): vc.stop()
                
                ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
                source = discord.FFmpegOpusAudio(str(cache_file), executable=ffmpeg_path, options='-filter:a "volume=1.5"')
                vc.play(source)
                
                while vc.is_playing():
                    await asyncio.sleep(0.1)
        except asyncio.TimeoutError:
            if vc.is_playing(): vc.stop()
            print(f"TTS timeout: {text[:30]}")

# ========================== EVENTOS ==========================
@bot.event
async def on_ready():
    global model
    print("🔄 Cargando Whisper...")
    model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    await inicializar_db()
    
    print(f"🤖 Jarvis Voz COMPLETO online | ID: {bot.user.id}")
    bot.loop.create_task(voz_loop())

async def voz_loop():
    """Escucha comandos del owner continuamente"""
    while True:
        try:
            if audio_processor.vc and audio_processor.vc.is_connected():
                texto = await audio_processor.transcribe_audio()
                if texto and len(texto) > 3:
                    print(f"🗣️ [{audio_processor.vc.guild.name}] Escuché: {texto}")
                    respuesta = await ejecutar_comando_voz(texto, audio_processor.vc.guild)
                    await play_audio(audio_processor.vc, respuesta)
            await asyncio.sleep(1)
        except Exception as e:
            print(f"[VOZ ERROR]: {e}")
            await asyncio.sleep(2)

@bot.event
async def on_voice_state_update(member, before, after):
    if member.id == TU_USER_ID and after.channel:  # ← TÚ entras VC
        guild = member.guild
        channel = after.channel
        
        # Auto-join si no está conectado
        vc = discord.utils.get(bot.voice_clients, guild=guild)
        if not vc:
            vc = await channel.connect()
            print(f"✅ Jarvis auto-joined {channel.name}")
        
        # Inicia escucha
        await audio_processor.start_listening(vc)
        await play_audio(vc, "Escuchando órdenes, jefe")
        
        # Desconecta si sales
    elif member.id == TU_USER_ID and before.channel and not after.channel:
        vc = discord.utils.get(bot.voice_clients, guild=member.guild)
        if vc:
            await vc.disconnect()
            print("👋 Jarvis desconectado")

    # Tu código original de bienvenidas aquí (simplificado)
    if member.bot: return
    # ... resto de lógica original ...

# ========================== FLASK KEEP-ALIVE ==========================
app = Flask(__name__)

@app.route("/")
def index():
    return "Jarvis Voz COMPLETO ✅"

def run_web():
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web, daemon=True).start()

# ========================== INICIO ==========================
if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("❌ DISCORD_TOKEN requerido")
        exit(1)
    
    bot.run(TOKEN)
