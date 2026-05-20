"""
JARVIS Bot — Escucha de Voz + Speech-to-Text (Vosk)
Con manejo robusto de errores y auto-recuperación.
"""
import asyncio
import json
import os
import sys
import array
import time
import logging
from collections import defaultdict
from pathlib import Path
import config

# Silenciar logs excesivos de voice_recv
logging.getLogger('discord.ext.voice_recv').setLevel(logging.WARNING)

# Intentar importar voice recv
try:
    from discord.ext import voice_recv
    VOICE_RECV_AVAILABLE = True
    print("✅ discord-ext-voice-recv disponible")
except ImportError:
    VOICE_RECV_AVAILABLE = False
    print("⚠️ discord-ext-voice-recv NO disponible — solo comandos por texto")

# Intentar importar Vosk
try:
    import vosk
    vosk.SetLogLevel(-1)
    VOSK_AVAILABLE = True
    print("✅ Vosk disponible")
except ImportError:
    VOSK_AVAILABLE = False
    print("⚠️ Vosk NO disponible — STT deshabilitado")


def resample_48k_stereo_to_16k_mono(pcm_bytes: bytes) -> bytes:
    """Convierte audio PCM 48kHz stereo a 16kHz mono para Vosk."""
    try:
        samples = array.array('h', pcm_bytes)
        mono = []
        for i in range(0, len(samples) - 1, 2):
            mono.append((samples[i] + samples[i + 1]) // 2)
        resampled = mono[::3]
        return array.array('h', resampled).tobytes()
    except Exception:
        return b''


class VoiceListener:
    def __init__(self, bot, on_command_callback):
        self.bot = bot
        self.on_command = on_command_callback
        self.model = None
        self.recognizers = {}
        self.pending_activation = {}
        self._enabled = VOICE_RECV_AVAILABLE and VOSK_AVAILABLE
        self._error_count = 0
        self._max_errors = 50  # Tolerar errores antes de reiniciar

        if self._enabled:
            self._load_model()

    @property
    def enabled(self):
        return self._enabled and self.model is not None

    def _load_model(self):
        model_path = str(config.VOSK_MODEL_DIR)
        if not os.path.exists(model_path):
            print(f"⚠️ Modelo Vosk no encontrado en: {model_path}")
            print("   Ejecuta: python setup_model.py")
            self._enabled = False
            return
        try:
            self.model = vosk.Model(model_path)
            print(f"✅ Modelo Vosk cargado: {model_path}")
        except Exception as e:
            print(f"❌ Error cargando modelo Vosk: {e}")
            self._enabled = False

    def get_recognizer(self, user_id: int):
        if user_id not in self.recognizers:
            self.recognizers[user_id] = vosk.KaldiRecognizer(
                self.model, config.VOSK_SAMPLE_RATE
            )
        return self.recognizers[user_id]

    def reset_recognizer(self, user_id: int):
        if user_id in self.recognizers:
            del self.recognizers[user_id]

    def get_voice_recv_client_class(self):
        if self.enabled:
            return voice_recv.VoiceRecvClient
        return None

    def create_sink(self):
        if not self.enabled:
            return None
        self._error_count = 0  # Reset on new sink
        return voice_recv.BasicSink(self._on_audio_data)

    def _on_audio_data(self, user, data):
        """Callback sincrónico — maneja errores sin crashear."""
        if user is None or user.bot:
            return

        try:
            # Verificar que data.pcm existe y tiene contenido
            if not hasattr(data, 'pcm') or not data.pcm:
                return

            audio_16k = resample_48k_stereo_to_16k_mono(data.pcm)
            if not audio_16k:
                return

            rec = self.get_recognizer(user.id)
            if rec.AcceptWaveform(audio_16k):
                result = json.loads(rec.Result())
                text = result.get("text", "").strip()
                if text and len(text) > 1:
                    print(f"[STT] {user.display_name}: '{text}'")
                    self._handle_text(user, text)

            # Reset error count on success
            self._error_count = 0

        except Exception as e:
            self._error_count += 1
            if self._error_count <= 3:
                print(f"[VOICE LISTENER ERROR #{self._error_count}] {e}")
            # Reset recognizer for this user on error
            self.reset_recognizer(user.id)

    def _handle_text(self, user, text: str):
        """Detecta palabra de activación 'Jarvis'."""
        text_lower = text.lower().strip()

        activation_words = [config.ACTIVATION_WORD] + config.ACTIVATION_ALIASES
        activated = False

        for word in activation_words:
            if word in text_lower:
                activated = True
                idx = text_lower.index(word)
                command_text = text[idx + len(word):].strip()
                command_text = command_text.lstrip(",.:;!¡¿? ")

                if command_text:
                    self._dispatch_command(user, command_text)
                else:
                    self.pending_activation[user.id] = time.time()
                    self._dispatch_command(user, "")
                break

        if not activated:
            if user.id in self.pending_activation:
                elapsed = time.time() - self.pending_activation[user.id]
                if elapsed < 8.0:
                    del self.pending_activation[user.id]
                    self._dispatch_command(user, text)
                else:
                    del self.pending_activation[user.id]

    def _dispatch_command(self, user, text: str):
        if self.bot.loop and self.bot.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.on_command(user, text),
                self.bot.loop
            )

    def cleanup_user(self, user_id: int):
        self.reset_recognizer(user_id)
        self.pending_activation.pop(user_id, None)

    def cleanup_all(self):
        self.recognizers.clear()
        self.pending_activation.clear()
