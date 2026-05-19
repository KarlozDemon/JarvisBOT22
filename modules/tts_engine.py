"""
JARVIS Bot — Motor Text-to-Speech
Genera audio de voz con edge-tts y lo reproduce en Discord.
"""
import discord
import edge_tts
import asyncio
import os
import config


# Lock por guild para evitar superposiciones de audio
_guild_locks = {}


async def speak(voice_client: discord.VoiceClient, text: str):
    """Genera TTS y reproduce en el canal de voz."""
    if not voice_client or not voice_client.is_connected():
        return

    guild_id = voice_client.guild.id
    if guild_id not in _guild_locks:
        _guild_locks[guild_id] = asyncio.Lock()

    filename = f"tts_{guild_id}.mp3"

    try:
        async with _guild_locks[guild_id]:
            print(f"[TTS] {voice_client.guild.name}: {text}")

            # Cortar audio previo
            if voice_client.is_playing():
                voice_client.stop()

            # Generar audio con edge-tts
            communicate = edge_tts.Communicate(text, voice=config.TTS_VOICE)
            await communicate.save(filename)

            # Reproducir
            source = discord.FFmpegPCMAudio(
                filename,
                executable="ffmpeg",
                options=f'-filter:a "volume={config.TTS_VOLUME}"'
            )
            voice_client.play(source)

            # Esperar a que termine
            while voice_client.is_playing():
                await asyncio.sleep(0.2)
            await asyncio.sleep(0.2)

    except Exception as e:
        print(f"[TTS ERROR] {e}")
    finally:
        try:
            if os.path.exists(filename):
                os.remove(filename)
        except Exception:
            pass


async def speak_quick(voice_client: discord.VoiceClient, text: str):
    """Habla sin esperar el lock — para respuestas inmediatas cortas."""
    if not voice_client or not voice_client.is_connected():
        return
    filename = f"tts_quick_{voice_client.guild.id}.mp3"
    try:
        if voice_client.is_playing():
            voice_client.stop()
        communicate = edge_tts.Communicate(text, voice=config.TTS_VOICE)
        await communicate.save(filename)
        voice_client.play(discord.FFmpegPCMAudio(
            filename, executable="ffmpeg",
            options=f'-filter:a "volume={config.TTS_VOLUME}"'
        ))
        while voice_client.is_playing():
            await asyncio.sleep(0.2)
    except Exception as e:
        print(f"[TTS QUICK ERROR] {e}")
    finally:
        try:
            if os.path.exists(filename):
                os.remove(filename)
        except Exception:
            pass
