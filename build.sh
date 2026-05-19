#!/usr/bin/env bash
# ========================== JARVIS Bot — Build Script para Render ==========================

set -e

echo "🔧 Instalando dependencias del sistema..."
apt-get update -qq && apt-get install -y -qq ffmpeg libopus0 libsodium23 2>/dev/null || true

echo "📦 Instalando dependencias de Python..."
pip install --upgrade pip
pip install -r requirements.txt

echo "📥 Descargando modelo de voz Vosk..."
python setup_model.py

echo "✅ Build completo — JARVIS listo para iniciar"
