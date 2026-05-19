"""
JARVIS Bot — Configuración Central
"""
import os
from pathlib import Path

# ========================== DISCORD ==========================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# ========================== GEMINI AI (OPCIONAL) =============
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# ========================== ACTIVACIÓN =======================
ACTIVATION_WORD = "jarvis"
ACTIVATION_ALIASES = ["jarvi", "yarvis", "jarves", "jarbis", "jarbus"]

# ========================== VOZ TTS ==========================
TTS_VOICE = "es-MX-JorgeNeural"       # Voz masculina tipo JARVIS
TTS_VOICE_FALLBACK = "es-ES-AlvaroNeural"
TTS_VOLUME = "2.0"

# ========================== VOZ STT (VOSK) ===================
VOSK_MODEL_DIR = Path(__file__).parent / "vosk-model-small-es-0.42"
VOSK_MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip"
VOSK_SAMPLE_RATE = 16000

# ========================== TIMEZONE =========================
TIMEZONE = "America/Lima"

# ========================== SERVIDOR =========================
# Flask keep-alive para Render
FLASK_PORT = int(os.getenv("PORT", "10000"))

# ========================== PATHS ============================
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_FILE = DATA_DIR / "usuarios_frecuentes.json"
