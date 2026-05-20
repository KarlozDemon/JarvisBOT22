"""
╔══════════════════════════════════════════════════════════════╗
║                    J.A.R.V.I.S.                              ║
║         Just A Rather Very Intelligent System                ║
║                                                              ║
║  Bot de Discord con control total por voz.                   ║
║  Escucha → Transcribe → Entiende → Ejecuta → Responde       ║
║                                                              ║
║  Solo responde cuando le dices "Jarvis".                     ║
╚══════════════════════════════════════════════════════════════╝
"""
import discord
import asyncio
import os
import sys
import threading
from flask import Flask

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from modules import tts_engine
from modules import command_parser
from modules import server_manager
from modules.voice_listener import VoiceListener

# ========================== DISCORD SETUP =========================

intents = discord.Intents.all()
bot = discord.Client(intents=intents)

# Estado global
voice_listener = None
guild_connect_locks = {}


# ========================== CONEXIÓN DE VOZ =======================

async def ensure_connected(target_channel: discord.VoiceChannel):
    """Conectar al canal de voz con escucha activa."""
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
            except Exception:
                try:
                    await vc.disconnect(force=True)
                except Exception:
                    pass

        # Conectar con VoiceRecvClient si STT está disponible
        connect_kwargs = {"reconnect": True, "timeout": 10}
        recv_cls = None
        if voice_listener and voice_listener.enabled:
            recv_cls = voice_listener.get_voice_recv_client_class()
            if recv_cls:
                connect_kwargs["cls"] = recv_cls

        try:
            vc = await target_channel.connect(**connect_kwargs)
            if recv_cls and voice_listener and voice_listener.enabled:
                sink = voice_listener.create_sink()
                if sink:
                    try:
                        vc.listen(sink)
                        print(f"[LISTENER] Escuchando en: {target_channel.name}")
                    except Exception as e:
                        print(f"[WARN] No se pudo iniciar escucha: {e}")
            return vc
        except Exception as e:
            print(f"[ERROR] connect falló: {e}")
            try:
                tmp = discord.utils.get(bot.voice_clients, guild=target_channel.guild)
                if tmp:
                    await tmp.disconnect(force=True)
            except Exception:
                pass
            try:
                vc = await target_channel.connect(**connect_kwargs)
                if recv_cls and voice_listener and voice_listener.enabled:
                    sink = voice_listener.create_sink()
                    if sink:
                        try:
                            vc.listen(sink)
                        except Exception:
                            pass
                return vc
            except Exception as e2:
                print(f"[ERROR] segundo connect falló: {e2}")
                return None


# ========================== HANDLER DE COMANDOS DE VOZ ============

async def on_voice_command(user, text: str):
    """Callback cuando se detecta 'Jarvis' + comando por voz."""
    member = None
    guild = None
    voice_channel = None

    for g in bot.guilds:
        m = g.get_member(user.id)
        if m and m.voice and m.voice.channel:
            member = m
            guild = g
            voice_channel = m.voice.channel
            break

    if not member or not guild:
        return

    command = command_parser.parse_command(text)
    if not command:
        return

    print(f"[COMMAND] {member.display_name}: {command['action']} → {command['params']}")

    response = await server_manager.execute(command, member, guild, voice_channel)

    vc = discord.utils.get(bot.voice_clients, guild=guild)
    if vc and vc.is_connected():
        await tts_engine.speak(vc, response)


# ========================== EVENTOS DE DISCORD ====================

@bot.event
async def on_ready():
    global voice_listener

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║  JARVIS Online                                               ║
║  Usuario: {bot.user}
║  Servidores: {len(bot.guilds)}
╚══════════════════════════════════════════════════════════════╝
    """)

    voice_listener = VoiceListener(bot, on_voice_command)
    if voice_listener.enabled:
        print("🎤 Sistema de escucha por voz: ACTIVO")
    else:
        print("🎤 Sistema de escucha por voz: INACTIVO (solo texto)")

    # Auto-unirse a canales de voz que ya tengan gente
    for guild in bot.guilds:
        for vc_channel in guild.voice_channels:
            humans = [m for m in vc_channel.members if not m.bot]
            if humans:
                print(f"[AUTO-JOIN] Uniéndose a {vc_channel.name} ({guild.name})")
                await ensure_connected(vc_channel)
                break  # Solo un canal por guild


@bot.event
async def on_voice_state_update(member, before, after):
    """Solo se usa para unirse/seguir al canal donde haya gente. Sin saludos."""
    if member.bot:
        return

    after_ch = after.channel
    before_ch = before.channel

    # Alguien entró a un canal → bot se une silenciosamente
    if after_ch and (before_ch != after_ch):
        me = member.guild.me
        if me:
            perms = after_ch.permissions_for(me)
            if not perms.connect or not perms.speak:
                return

        vc = discord.utils.get(bot.voice_clients, guild=member.guild)
        if not vc or not vc.is_connected():
            # Bot no está en ningún canal → unirse
            await ensure_connected(after_ch)
        # Si el bot ya está en otro canal, se queda donde está

    # Si el canal del bot se queda vacío, moverse al canal donde haya gente
    vc = discord.utils.get(bot.voice_clients, guild=member.guild)
    if vc and vc.is_connected() and vc.channel:
        humans_in_bot_channel = [m for m in vc.channel.members if not m.bot]
        if not humans_in_bot_channel:
            # Buscar otro canal con gente
            for voice_ch in member.guild.voice_channels:
                humans = [m for m in voice_ch.members if not m.bot]
                if humans:
                    try:
                        await vc.move_to(voice_ch)
                        print(f"[MOVE] Bot se movió a {voice_ch.name}")
                        # Re-iniciar escucha después de moverse
                        if voice_listener and voice_listener.enabled:
                            sink = voice_listener.create_sink()
                            if sink:
                                try:
                                    vc.listen(sink)
                                except Exception:
                                    pass
                    except Exception:
                        pass
                    return
            # No hay nadie en ningún canal → el bot se queda esperando


# ========================== COMANDOS POR TEXTO ====================

@bot.event
async def on_message(message):
    """Comandos por texto como fallback."""
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

    print(f"[TEXT CMD] {member.display_name}: {command['action']} → {command['params']}")

    voice_channel = None
    if hasattr(member, 'voice') and member.voice:
        voice_channel = member.voice.channel

    response = await server_manager.execute(command, member, guild, voice_channel)

    await message.channel.send(f"🤖 **JARVIS:** {response}")

    vc = discord.utils.get(bot.voice_clients, guild=guild)
    if vc and vc.is_connected():
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
