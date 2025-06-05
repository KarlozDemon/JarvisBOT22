import discord
import edge_tts
import asyncio
import os
import re
import unicodedata
import random
from flask import Flask
import threading

intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True
intents.members = True

bot = discord.Client(intents=intents)

# ID del canal objetivo
CANAL_OBJETIVO_ID = 1375567307782357048  # Reemplaza por tu canal real

# Lock para evitar reproducir varios audios a la vez
audio_lock = asyncio.Lock()

def limpiar_nombre(nombre):
    nombre_original = nombre.lower()
    if "jose is back" in nombre_original or "jᴏꜱᴇ ɪꜱ ʙᴀᴄᴋ" in nombre_original:
        return "José"
    nombre = re.sub(r'[^\w\s]', '', nombre)
    nombre = unicodedata.normalize('NFKD', nombre).encode('ASCII', 'ignore').decode('ASCII')
    nombre = ' '.join(nombre.split())
    nombre = nombre.lower().capitalize()
    if len(nombre) <= 2:
        return "Invitado"
    return nombre

async def play_audio(vc, text):
    async with audio_lock:
        filename = "tts.mp3"
        communicate = edge_tts.Communicate(text, voice="es-ES-ElviraNeural")
        await communicate.save(filename)
        vc.play(discord.FFmpegPCMAudio(filename, executable="ffmpeg"))

        while vc.is_playing():
            await asyncio.sleep(1)
        
        # Espera un poco más para asegurar que ffmpeg libere el archivo
        await asyncio.sleep(1)
        os.remove(filename)

@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return

    nombre_limpio = limpiar_nombre(member.display_name)
    voice_client = discord.utils.get(bot.voice_clients, guild=member.guild)

    # Frases dinámicas
    frases_bienvenida = [
        f"{nombre_limpio} ha llegado. ¡Atención!",
        f"¡Bienvenido {nombre_limpio}!",
        f"{nombre_limpio} se ha conectado. ¡Saludos!",
        f"{nombre_limpio} está ahora con nosotros."
    ]
    frases_despedida = [
        f"{nombre_limpio} se ha ido. Hasta luego.",
        f"{nombre_limpio} se ha desconectado. ¡Adiós!",
        f"¡Hasta pronto {nombre_limpio}!",
        f"{nombre_limpio} ha abandonado el canal."
    ]

    # Caso: usuario entra al canal supervisado
    if after.channel and after.channel.id == CANAL_OBJETIVO_ID and (before.channel != after.channel):
        if voice_client is None or not voice_client.is_connected():
            voice_client = await after.channel.connect()
        text = random.choice(frases_bienvenida)
        await play_audio(voice_client, text)

    # Caso: usuario se fue o se movió a otro canal desde el canal supervisado
    if before.channel and before.channel.id == CANAL_OBJETIVO_ID and after.channel != before.channel:
        if voice_client and voice_client.is_connected():
            text = random.choice(frases_despedida)
            await play_audio(voice_client, text)

    # Revisión final: ¿queda solo el bot?
    voice_client = discord.utils.get(bot.voice_clients, guild=member.guild)
    if voice_client and voice_client.is_connected():
        usuarios_humanos = [m for m in voice_client.channel.members if not m.bot]
        if not usuarios_humanos:
            await voice_client.disconnect()

# =============== FLASK para simular el puerto ==============
app = Flask(__name__)

@app.route('/')
def index():
    return "¡Estoy vivo, Render!"

def run_web():
    app.run(host='0.0.0.0', port=10000)  # El puerto que Render espera

# Lanzamos el webserver falso en un hilo separado
threading.Thread(target=run_web).start()

# Token: lo tomamos de la variable de entorno para mayor seguridad
bot.run(os.getenv("DISCORD_TOKEN"))
