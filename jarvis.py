"""
╔══════════════════════════════════════════════════════════════╗
║                    J.A.R.V.I.S.                              ║
║         Just A Rather Very Intelligent System                ║
║                                                              ║
║  Bot de Discord con control total por voz.                   ║
║  Escucha → Transcribe → Entiende → Ejecuta → Responde       ║
╚══════════════════════════════════════════════════════════════╝
"""
import discord
import asyncio
import os
import sys
import atexit
import threading
from datetime import datetime
from flask import Flask
import pytz

# Agregar directorio actual al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from modules import tts_engine
from modules import greeter
from modules import command_parser
from modules import server_manager
from modules.voice_listener import VoiceListener

# ========================== DISCORD SETUP =========================

intents = discord.Intents.all()

bot = discord.Client(intents=intents)

# ========================== ESTADO GLOBAL =========================

# Registrar timestamps de entrada de usuarios
entradas_usuarios = {}

# Voice listener (STT)
voice_listener = None

# Locks de conexión por guild
guild_connect_locks = {}

# ========================== CONEXIÓN DE VOZ =======================


async def ensure_connected(target_channel: discord.VoiceChannel, use_recv=False):
    """Conectar al canal de voz de forma robusta."""
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
                print(f"[WARN] move_to falló: {e}")
                try:
                    await vc.disconnect(force=True)
                except Exception:
                    pass

        # Conectar con VoiceRecvClient si STT está habilitado
        connect_kwargs = {"reconnect": True, "timeout": 10}
        recv_cls = None
        if use_recv and voice_listener and voice_listener.enabled:
            recv_cls = voice_listener.get_voice_recv_client_class()
            if recv_cls:
                connect_kwargs["cls"] = recv_cls

        try:
            vc = await target_channel.connect(**connect_kwargs)

            # Iniciar escucha si usamos VoiceRecvClient
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
            # Reintento
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
    """
    Callback del VoiceListener cuando se detecta un comando por voz.
    user: discord.User (del voice_recv)
    text: texto del comando (sin la palabra de activación)
    """
    # Encontrar el guild y member
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
        print(f"[WARN] No se encontró guild/member para {user}")
        return

    # Parsear el comando
    command = command_parser.parse_command(text)
    if not command:
        return

    print(f"[COMMAND] {member.display_name}: {command['action']} → {command['params']}")

    # Ejecutar el comando
    response = await server_manager.execute(command, member, guild, voice_channel)

    # Responder por voz
    vc = discord.utils.get(bot.voice_clients, guild=guild)
    if vc and vc.is_connected():
        await tts_engine.speak(vc, response)
    else:
        print(f"[WARN] No hay voice client para responder en {guild.name}")


# ========================== EVENTOS DE DISCORD ====================


@bot.event
async def on_ready():
    global voice_listener

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║  JARVIS Online                                               ║
║  Usuario: {bot.user}
║  ID: {bot.user.id}
║  Servidores: {len(bot.guilds)}
╚══════════════════════════════════════════════════════════════╝
    """)

    # Inicializar Voice Listener (STT)
    voice_listener = VoiceListener(bot, on_voice_command)
    if voice_listener.enabled:
        print("🎤 Sistema de escucha por voz: ACTIVO")
    else:
        print("🎤 Sistema de escucha por voz: INACTIVO (solo texto)")

    # Cargar base de datos de usuarios
    greeter.inicializar_db()


@bot.event
async def on_voice_state_update(member, before, after):
    """Maneja entradas/salidas de canales de voz."""
    if member.bot:
        return

    after_ch = after.channel
    before_ch = before.channel
    nombre = greeter.limpiar_nombre(member.display_name)
    ahora = datetime.now(pytz.timezone(config.TIMEZONE))

    # Verificar permisos del bot
    try:
        me = member.guild.me or await member.guild.fetch_member(bot.user.id)
    except Exception:
        me = None

    # ========== ENTRADA ==========
    if after_ch and (before_ch != after_ch):
        if me:
            perms = after_ch.permissions_for(me)
            if not perms.connect or not perms.speak:
                print(f"[PERMISOS] Sin acceso a: {after_ch.name}")
                return

        # Incrementar visitas
        veces = greeter.incrementar_veces(member.guild.id, member.id)
        print(f"[ENTRADA] {nombre} → {after_ch.name} (visita #{veces})")

        # Conectar al canal (con escucha de voz si está disponible)
        vc = await ensure_connected(after_ch, use_recv=True)
        if not vc:
            print(f"[ERROR] No pude conectar a: {after_ch.name}")
            return

        entradas_usuarios[(member.guild.id, member.id)] = ahora

        # Generar saludo
        text = greeter.frase_bienvenida(nombre, veces)

        # Si hay muchos usuarios, saludo especial
        try:
            miembros = list(getattr(after_ch, "members", []))
            num_humanos = len([m for m in miembros if not m.bot])
            if num_humanos >= 20:
                text = f"¡Wow, esto se está llenando! Bienvenido {nombre}, saludos a todos."
        except Exception:
            pass

        await tts_engine.speak(vc, text)

    # ========== SALIDA ==========
    if before_ch and after_ch != before_ch:
        print(f"[SALIDA] {nombre} ← {before_ch.name}")

        vc = discord.utils.get(bot.voice_clients, guild=member.guild)
        if vc and vc.is_connected():
            entrada = entradas_usuarios.pop((member.guild.id, member.id), None)
            if entrada:
                duracion = (ahora - entrada).total_seconds()
                if duracion < 10:
                    text = greeter.frases_rapida[
                        hash(nombre) % len(greeter.frases_rapida)
                    ].format(nombre=nombre)
                else:
                    text = greeter.frase_despedida(nombre)
            else:
                text = f"{nombre} se ha desconectado. ¡Cuídate!"
            await tts_engine.speak(vc, text)

        # Limpiar recursos del voice listener
        if voice_listener:
            voice_listener.cleanup_user(member.id)

    # ========== INICIO STREAM ==========
    if after_ch:
        if not before.self_stream and after.self_stream:
            import random
            texto = random.choice(greeter.frases_inicio_stream).format(nombre=nombre)
            vc = discord.utils.get(bot.voice_clients, guild=member.guild)
            if vc and vc.is_connected():
                await tts_engine.speak(vc, texto)

    # ========== FIN STREAM ==========
    if before_ch:
        if before.self_stream and not after.self_stream:
            import random
            texto = random.choice(greeter.frases_fin_stream).format(nombre=nombre)
            vc = discord.utils.get(bot.voice_clients, guild=member.guild)
            if vc and vc.is_connected():
                await tts_engine.speak(vc, texto)

    # ========== DESCONEXIÓN INTELIGENTE ==========
    vc = discord.utils.get(bot.voice_clients, guild=member.guild)
    if vc and vc.is_connected() and vc.channel:
        try:
            miembros = list(getattr(vc.channel, "members", []))
        except Exception:
            miembros = []
        humanos = [m for m in miembros if not m.bot]

        if len(humanos) == 1:
            text = f"{humanos[0].display_name}, parece que ahora estás solo. ¡Aquí sigo contigo!"
            await tts_engine.speak(vc, text)
        elif not humanos:
            text = "Parece que me quedé solito aquí…"
            await tts_engine.speak(vc, text)
            try:
                if vc.is_playing():
                    vc.stop()
            except Exception:
                pass
            if voice_listener:
                voice_listener.cleanup_all()
            await vc.disconnect()


# ========================== COMANDOS POR TEXTO (FALLBACK) =========


@bot.event
async def on_message(message):
    """Permite comandos por texto como fallback."""
    if message.author.bot:
        return

    content = message.content.strip().lower()

    # Detectar si el mensaje empieza con "jarvis" o menciona al bot
    activated = False
    command_text = ""

    for alias in [config.ACTIVATION_WORD] + config.ACTIVATION_ALIASES:
        if content.startswith(alias):
            activated = True
            command_text = message.content[len(alias):].strip()
            command_text = command_text.lstrip(",.:;!¡¿? ")
            break

    if bot.user in message.mentions:
        activated = True
        # Remover la mención del texto
        command_text = message.content
        for mention in [f"<@{bot.user.id}>", f"<@!{bot.user.id}>"]:
            command_text = command_text.replace(mention, "").strip()

    if not activated:
        return

    # Parsear y ejecutar
    command = command_parser.parse_command(command_text)
    if not command:
        return

    guild = message.guild
    member = message.author

    print(f"[TEXT CMD] {member.display_name}: {command['action']} → {command['params']}")

    # Encontrar el canal de voz del usuario (si está en uno)
    voice_channel = None
    if hasattr(member, 'voice') and member.voice:
        voice_channel = member.voice.channel

    response = await server_manager.execute(command, member, guild, voice_channel)

    # Responder por texto
    await message.channel.send(f"🤖 **JARVIS:** {response}")

    # También responder por voz si el bot está en un canal de voz
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

atexit.register(greeter.guardar_db)

print("""
╔══════════════════════════════════════════════════════════════╗
║              🚀 JARVIS — Iniciando sistemas...               ║
╚══════════════════════════════════════════════════════════════╝
""")

if __name__ == "__main__":
    TOKEN = config.DISCORD_TOKEN
    if not TOKEN:
        print("❌ Error: Variable de entorno DISCORD_TOKEN no definida.")
        print("   Configura: export DISCORD_TOKEN='tu_token_aquí'")
        sys.exit(1)

    # Cargar opus si es necesario
    try:
        if not discord.opus.is_loaded():
            discord.opus.load_opus("libopus.so.0")
    except Exception as e:
        print(f"[WARN] Opus: {e}")

    bot.run(TOKEN)
