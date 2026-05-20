"""
╔══════════════════════════════════════════════════════════════╗
║                    J.A.R.V.I.S.                              ║
║         Just A Rather Very Intelligent System                ║
║                                                              ║
║  Bot de Discord — Comandos por texto, respuestas por voz.    ║
║  Escribe "jarvis [comando]" → Bot responde con TTS.          ║
╚══════════════════════════════════════════════════════════════╝
"""
import discord
import asyncio
import os
import sys
import threading
import time
from flask import Flask

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from modules import tts_engine
from modules import command_parser
from modules import server_manager

# ========================== DISCORD SETUP =========================

intents = discord.Intents.all()
bot = discord.Client(intents=intents)

# Lock por guild para evitar conexiones dobles
_connect_locks = {}
_connecting = set()  # guilds que están en proceso de conexión


# ========================== CONEXIÓN DE VOZ =======================

async def ensure_connected(target_channel: discord.VoiceChannel):
    """Conectar al canal de voz de forma segura. Sin voice_recv."""
    gid = target_channel.guild.id

    # Si ya estamos conectando, no hacer nada
    if gid in _connecting:
        return None

    if gid not in _connect_locks:
        _connect_locks[gid] = asyncio.Lock()

    async with _connect_locks[gid]:
        _connecting.add(gid)
        try:
            vc = discord.utils.get(bot.voice_clients, guild=target_channel.guild)

            if vc and vc.is_connected():
                if vc.channel and vc.channel.id == target_channel.id:
                    return vc
                try:
                    await vc.move_to(target_channel)
                    await asyncio.sleep(1)
                    return vc
                except Exception:
                    try:
                        await vc.disconnect(force=True)
                        await asyncio.sleep(1)
                    except Exception:
                        pass

            try:
                vc = await target_channel.connect(reconnect=True, timeout=15)
                await asyncio.sleep(1)
                print(f"[CONNECTED] {target_channel.name}")
                return vc
            except Exception as e:
                print(f"[ERROR] connect: {e}")
                # Limpiar conexión fallida
                try:
                    tmp = discord.utils.get(bot.voice_clients, guild=target_channel.guild)
                    if tmp:
                        await tmp.disconnect(force=True)
                except Exception:
                    pass
                return None
        finally:
            _connecting.discard(gid)


def _get_category_voice_channels(guild):
    """Retorna solo canales de voz en la categoría configurada."""
    return [ch for ch in guild.voice_channels
            if ch.category_id == config.VOICE_CATEGORY_ID]


# ========================== EVENTOS DE DISCORD ====================

@bot.event
async def on_ready():
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║  JARVIS Online                                               ║
║  Usuario: {bot.user}
║  Servidores: {len(bot.guilds)}
║  Categoría: {config.VOICE_CATEGORY_ID}
║  Modo: Texto → Voz (TTS)                                    ║
╚══════════════════════════════════════════════════════════════╝
    """)

    # Esperar antes de auto-conectar
    await asyncio.sleep(5)
    for guild in bot.guilds:
        vc = discord.utils.get(bot.voice_clients, guild=guild)
        if vc and vc.is_connected():
            continue
        for vc_channel in _get_category_voice_channels(guild):
            humans = [m for m in vc_channel.members if not m.bot]
            if humans:
                print(f"[AUTO-JOIN] {vc_channel.name} ({guild.name})")
                await ensure_connected(vc_channel)
                break


@bot.event
async def on_voice_state_update(member, before, after):
    """Unirse/moverse/irse SOLO en la categoría asignada."""
    if member.bot:
        return

    guild = member.guild
    after_ch = after.channel
    before_ch = before.channel

    # Solo actuar si involucra nuestra categoría
    after_in_cat = after_ch and after_ch.category_id == config.VOICE_CATEGORY_ID
    before_in_cat = before_ch and before_ch.category_id == config.VOICE_CATEGORY_ID
    if not after_in_cat and not before_in_cat:
        return

    # Esperar para evitar race conditions
    await asyncio.sleep(2)

    vc = discord.utils.get(bot.voice_clients, guild=guild)

    # Bot no está conectado → unirse al canal con gente
    if not vc or not vc.is_connected():
        if after_in_cat:
            humans = [m for m in after_ch.members if not m.bot]
            if humans:
                await ensure_connected(after_ch)
        return

    # Bot está conectado → verificar si queda gente
    if vc.channel:
        humans_here = [m for m in vc.channel.members if not m.bot]
        if humans_here:
            return  # Hay gente, quedarse

        # Buscar otro canal en la categoría con gente
        for voice_ch in _get_category_voice_channels(guild):
            if voice_ch.id == vc.channel.id:
                continue
            humans = [m for m in voice_ch.members if not m.bot]
            if humans:
                try:
                    await vc.move_to(voice_ch)
                    print(f"[MOVE] → {voice_ch.name}")
                    await asyncio.sleep(1)
                except Exception as e:
                    print(f"[MOVE ERROR] {e}")
                return

        # Nadie en la categoría → desconectarse
        print(f"[LEAVE] Nadie en la categoría")
        try:
            if vc.is_playing():
                vc.stop()
            await vc.disconnect()
        except Exception:
            pass


# ========================== COMANDOS POR TEXTO ====================

@bot.event
async def on_message(message):
    """Escribe 'jarvis [comando]' y responde por texto + voz."""
    if message.author.bot:
        return

    content = message.content.strip().lower()
    activated = False
    command_text = ""

    for alias in [config.ACTIVATION_WORD] + config.ACTIVATION_ALIASES:
        if content.startswith(alias):
            activated = True
            command_text = message.content[len(alias):].strip().lstrip(",.:;!¡¿? ")
            break

    if bot.user in message.mentions:
        activated = True
        command_text = message.content
        for mention in [f"<@{bot.user.id}>", f"<@!{bot.user.id}>"]:
            command_text = command_text.replace(mention, "").strip()

    if not activated:
        return

    command = command_parser.parse_command(command_text)
    if not command:
        return

    guild = message.guild
    member = message.author

    print(f"[CMD] {member.display_name}: {command['action']} → {command['params']}")

    voice_channel = None
    if hasattr(member, 'voice') and member.voice:
        voice_channel = member.voice.channel

    response = await server_manager.execute(command, member, guild, voice_channel)

    await message.channel.send(f"🤖 **JARVIS:** {response}")

    # Responder con TTS si está en voz
    vc = discord.utils.get(bot.voice_clients, guild=guild)
    if vc and vc.is_connected():
        await tts_engine.speak(vc, response)
    elif voice_channel and voice_channel.category_id == config.VOICE_CATEGORY_ID:
        # Si el usuario está en la categoría pero el bot no, unirse
        vc = await ensure_connected(voice_channel)
        if vc:
            await asyncio.sleep(0.5)
            await tts_engine.speak(vc, response)


# ========================== FLASK KEEP-ALIVE ======================

flask_app = Flask(__name__)

@flask_app.route('/')
def index():
    return "🤖 JARVIS Online ✅"

@flask_app.route('/health')
def health():
    return {"status": "online", "bot": str(bot.user) if bot.user else "starting"}

def run_web():
    flask_app.run(host='0.0.0.0', port=config.FLASK_PORT)

threading.Thread(target=run_web, daemon=True).start()

# ========================== INICIO ================================

print("""
╔══════════════════════════════════════════════════════════════╗
║              🚀 JARVIS — Iniciando sistemas...               ║
╚══════════════════════════════════════════════════════════════╝
""")

if __name__ == "__main__":
    TOKEN = config.DISCORD_TOKEN
    if not TOKEN:
        print("❌ Error: Variable de entorno DISCORD_TOKEN no definida.")
        sys.exit(1)

    try:
        if not discord.opus.is_loaded():
            discord.opus.load_opus("libopus.so.0")
    except Exception as e:
        print(f"[WARN] Opus: {e}")

    bot.run(TOKEN)
