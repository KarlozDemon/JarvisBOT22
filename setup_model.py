"""
JARVIS Bot — Descargador del modelo Vosk para español.
Ejecutar: python setup_model.py
"""
import os
import sys
import zipfile
import urllib.request
import shutil
from pathlib import Path

MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip"
MODEL_DIR = Path(__file__).parent / "vosk-model-small-es-0.42"
ZIP_FILE = Path(__file__).parent / "vosk-model-small-es-0.42.zip"


def download_model():
    if MODEL_DIR.exists():
        print(f"✅ Modelo ya existe en: {MODEL_DIR}")
        return True

    print(f"📥 Descargando modelo Vosk español...")
    print(f"   URL: {MODEL_URL}")
    print(f"   Destino: {MODEL_DIR}")

    try:
        # Descargar
        def progress(block, block_size, total):
            downloaded = block * block_size
            if total > 0:
                pct = min(100, downloaded * 100 // total)
                bar = "█" * (pct // 2) + "░" * (50 - pct // 2)
                sys.stdout.write(f"\r   [{bar}] {pct}% ({downloaded // 1024 // 1024}MB)")
                sys.stdout.flush()

        urllib.request.urlretrieve(MODEL_URL, str(ZIP_FILE), reporthook=progress)
        print("\n✅ Descarga completa")

        # Extraer
        print("📦 Extrayendo modelo...")
        with zipfile.ZipFile(str(ZIP_FILE), 'r') as z:
            z.extractall(str(Path(__file__).parent))
        print(f"✅ Modelo extraído en: {MODEL_DIR}")

        # Limpiar zip
        if ZIP_FILE.exists():
            ZIP_FILE.unlink()
            print("🗑️ ZIP eliminado")

        return True

    except Exception as e:
        print(f"\n❌ Error descargando modelo: {e}")
        # Limpiar archivos parciales
        if ZIP_FILE.exists():
            ZIP_FILE.unlink()
        if MODEL_DIR.exists():
            shutil.rmtree(MODEL_DIR)
        return False


if __name__ == "__main__":
    success = download_model()
    if success:
        print("\n🎉 ¡Modelo listo! Puedes iniciar JARVIS con: python jarvis.py")
    else:
        print("\n❌ Falló la instalación del modelo.")
        print("   Descárgalo manualmente de: https://alphacephei.com/vosk/models")
        sys.exit(1)
