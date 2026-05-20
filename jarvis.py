"""
╔══════════════════════════════════════════════════════════════╗
║                    J.A.R.V.I.S.                              ║
║         Just A Rather Very Intelligent System                ║
║                                                              ║
║  Escribe "jarvis [comando]" → Responde por texto + voz.      ║
║  Escribe "jarvis ven" → Se une a tu canal de voz.            ║
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

# ========================== DISCORD SETUP =========================

intents = discord.Intents.all()
bot = discord.Client(intents=intents)

# Un solo flag por guild para evitar conexiones dobles
_busy = set()


# ========================== CONEXIÓN DE VOZ =======================

async def safe_join(channel: discord.VoiceChannel):
    """Conectar al canal de forma segura. UNA sola conexión a la vez."""
    gid = channel.guild.id
    if gid in _busy:
        return None

    _busy.add(gid)
    try:
        # Si ya estamos ahí, retornar
        vc = discord.utils.get(bot.voice_clients, guild=channel.guild)
        if vc and vc.is_connected():
            if vc.channel.id == channel.id:
                return vc
            # Moverse al otro canal
            await vc.move_to(channel)
            await asyncio.sleep(1)
            print(f"[MOVE] → {channel.name}")
            return vc

        # Conectar nuevo
        vc = await channel.connect(reconnect=True, timeout=15)
        await asyncio.sleep(1)
        print(f"[JOIN] → {channel.name}")
        return vc

    except Exception as e:
        print(f"[JOIN ERROR] {e}")
        try:
            tmp = discord.utils.get(bot.voice_clients, guild=channel.guild)
            if tmp:
                await tmp.disconnect(force=True)
        except Exception:
            pass
        return None
    finally:
        _busy.discard(gid)


def in_category(channel):
    """Verifica si un canal está en la categoría configurada."""
    return channel and channel.category_id == config.VOICE_CATEGORY_ID


# ========================== EVENTOS =======================

@bot.event
async def on_ready():
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║  JARVIS Online ✅                                            ║
║  Usuario: {bot.user}
║  Servidores: {len(bot.guilds)}
║  Categoría: {config.VOICE_CATEGORY_ID}
║  Escribe: jarvis ven  (para que entre a tu canal)            ║
╚══════════════════════════════════════════════════════════════╝
    """)


@bot.event
async def on_voice_state_update(member, before, after):
    """Si alguien entra a la categoría y el bot no está, se une."""
    if member.bot:
        return

    guild = member.guild

    # Solo si entró a un canal de la categoría
    if not after.channel or not in_category(after.channel):
        # Si salió y el canal del bot quedó vacío → irse
        vc = discord.utils.get(bot.voice_clients, guild=guild)
        if vc and vc.is_connected() and vc.channel:
            await asyncio.sleep(2)
            humans = [m for m in vc.channel.members if not m.bot]
            if not humans:
                # Buscar otro canal en la categoría
                for ch in guild.voice_channels:
                    if in_category(ch) and ch.id != vc.channel.id:
                        h = [m for m in ch.members if not m.bot]
                        if h:
                            await safe_join(ch)
                            return
                # Nadie → irse
                print("[LEAVE] Nadie en la categoría")
                try:
                    await vc.disconnect()
                except Exception:
                    pass
        return

    # Alguien entró a canal en la categoría → unirse si no estamos
    vc = discord.utils.get(bot.voice_clients, guild=guild)
    if vc and vc.is_connected():
        return  # Ya estamos en un canal

    # Esperar antes de unirse
    await asyncio.sleep(3)
    # Verificar que sigue ahí
    if member.voice and member.voice.channel and in_category(member.voice.channel):
        await safe_join(member.voice.channel)


# ========================== COMANDOS POR TEXTO ====================

@bot.event
async def on_message(message):
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

    # Comando especial: "jarvis ven" → unirse al canal del usuario
    cmd_lower = command_text.lower().strip()
    if cmd_lower in ("ven", "unite", "entra", "conectate", "join", "venir"):
        if hasattr(message.author, 'voice') and message.author.voice and message.author.voice.channel:
            ch = message.author.voice.channel
            vc = await safe_join(ch)
            if vc:
                await message.channel.send("🤖 **JARVIS:** A sus órdenes, señor.")
                await tts_engine.speak(vc, "A sus órdenes, señor.")
            else:
                await message.channel.send("🤖 **JARVIS:** No pude conectarme, señor.")
        else:
            await message.channel.send("🤖 **JARVIS:** Debe estar en un canal de voz primero, señor.")
        return

    # Comando especial: "jarvis vete" → desconectarse
    if cmd_lower in ("vete", "sal", "desconectate", "leave", "fuera"):
        vc = discord.utils.get(bot.voice_clients, guild=message.guild)
        if vc:
            await vc.disconnect()
            await message.channel.send("🤖 **JARVIS:** Me retiro, señor.")
        else:
            await message.channel.send("🤖 **JARVIS:** No estoy en ningún canal, señor.")
        return

    # Parsear comando normal
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

    # TTS si está en voz
    vc = discord.utils.get(bot.voice_clients, guild=guild)
    if vc and vc.is_connected():
        await tts_engine.speak(vc, response)


# ========================== FLASK ======================

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
