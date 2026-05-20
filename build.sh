#!/usr/bin/env bash
set -e

echo "📦 Instalando dependencias de Python..."
pip install --upgrade pip
pip install -r requirements.txt

echo "📥 Descargando modelo de voz Vosk..."
python setup_model.py

echo "✅ Build completo — JARVIS listo"
