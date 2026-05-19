"""
JARVIS Bot — Escucha de Voz + Speech-to-Text (Vosk)
Captura audio de usuarios en Discord y lo transcribe a texto.
"""
import asyncio
import json
import os
import sys
import array
import time
from collections import defaultdict
from pathlib import Path
import config

# Intentar importar dependencias de voice recv
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
    vosk.SetLogLevel(-1)  # Silenciar logs de Vosk
    VOSK_AVAILABLE = True
    print("✅ Vosk disponible")
except ImportError:
    VOSK_AVAILABLE = False
    print("⚠️ Vosk NO disponible — STT deshabilitado")


def resample_48k_stereo_to_16k_mono(pcm_bytes: bytes) -> bytes:
    """Convierte audio PCM 48kHz stereo a 16kHz mono para Vosk."""
    samples = array.array('h', pcm_bytes)
    # Stereo → mono: promediar pares
    mono = []
    for i in range(0, len(samples) - 1, 2):
        mono.append((samples[i] + samples[i + 1]) // 2)
    # 48kHz → 16kHz: tomar cada 3er sample
    resampled = mono[::3]
    return array.array('h', resampled).tobytes()


class VoiceListener:
    """
    Escucha audio de usuarios en canales de voz y lo transcribe.
    Requiere: discord-ext-voice-recv + vosk
    """

    def __init__(self, bot, on_command_callback):
        """
        Args:
            bot: Instancia del bot de Discord
            on_command_callback: async función(member, text) llamada cuando
                                 se detecta un comando con palabra de activación
        """
        self.bot = bot
        self.on_command = on_command_callback
        self.model = None
        self.recognizers = {}
        self.last_text_time = defaultdict(float)
        self.pending_activation = {}  # user_id -> timestamp
        self._enabled = VOICE_RECV_AVAILABLE and VOSK_AVAILABLE

        if self._enabled:
            self._load_model()

    @property
    def enabled(self):
        return self._enabled and self.model is not None

    def _load_model(self):
        """Carga el modelo de Vosk para español."""
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
        """Obtiene o crea un reconocedor para un usuario."""
        if user_id not in self.recognizers:
            self.recognizers[user_id] = vosk.KaldiRecognizer(
                self.model, config.VOSK_SAMPLE_RATE
            )
        return self.recognizers[user_id]

    def reset_recognizer(self, user_id: int):
        """Resetea el reconocedor de un usuario."""
        if user_id in self.recognizers:
            del self.recognizers[user_id]

    def get_voice_recv_client_class(self):
        """Retorna la clase VoiceRecvClient si está disponible."""
        if self.enabled:
            return voice_recv.VoiceRecvClient
        return None

    def create_sink(self):
        """Crea un AudioSink para capturar audio."""
        if not self.enabled:
            return None
        return voice_recv.BasicSink(self._on_audio_data)

    def _on_audio_data(self, user, data):
        """
        Callback sincrónico llamado por voice_recv cuando llega audio.
        Se ejecuta en un thread diferente al event loop.
        """
        if user is None or user.bot:
            return

        try:
            # Resamplear audio
            audio_16k = resample_48k_stereo_to_16k_mono(data.pcm)

            # Alimentar al reconocedor
            rec = self.get_recognizer(user.id)
            if rec.AcceptWaveform(audio_16k):
                result = json.loads(rec.Result())
                text = result.get("text", "").strip()
                if text and len(text) > 1:
                    self._handle_text(user, text)
        except Exception as e:
            print(f"[VOICE LISTENER ERROR] {e}")

    def _handle_text(self, user, text: str):
        """Maneja texto transcrito — detecta palabra de activación."""
        text_lower = text.lower().strip()
        print(f"[STT] {user.display_name}: '{text}'")

        # Verificar si contiene la palabra de activación
        activation_words = [config.ACTIVATION_WORD] + config.ACTIVATION_ALIASES
        activated = False

        for word in activation_words:
            if word in text_lower:
                activated = True
                # Remover la palabra de activación del texto
                idx = text_lower.index(word)
                command_text = text[idx + len(word):].strip()
                command_text = command_text.lstrip(",.:;!¡¿? ")

                if command_text:
                    # Comando completo: "Jarvis mutea a pedro"
                    self._dispatch_command(user, command_text)
                else:
                    # Solo dijo "Jarvis" — esperar siguiente frase
                    self.pending_activation[user.id] = time.time()
                    self._dispatch_command(user, "")  # Respuesta de greeting
                break

        if not activated:
            # Si hay una activación pendiente (dijo "Jarvis" antes)
            if user.id in self.pending_activation:
                elapsed = time.time() - self.pending_activation[user.id]
                if elapsed < 8.0:  # 8 segundos de ventana
                    del self.pending_activation[user.id]
                    self._dispatch_command(user, text)
                else:
                    del self.pending_activation[user.id]

    def _dispatch_command(self, user, text: str):
        """Despacha el comando al event loop de asyncio."""
        if self.bot.loop and self.bot.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.on_command(user, text),
                self.bot.loop
            )

    def cleanup_user(self, user_id: int):
        """Limpia recursos de un usuario que se desconectó."""
        self.reset_recognizer(user_id)
        self.pending_activation.pop(user_id, None)

    def cleanup_all(self):
        """Limpia todos los recursos."""
        self.recognizers.clear()
        self.pending_activation.clear()
