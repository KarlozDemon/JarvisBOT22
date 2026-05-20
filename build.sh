#!/usr/bin/env bash
set -e

echo "📦 Instalando dependencias..."
pip install --upgrade pip
pip install -r requirements.txt

echo "✅ Build completo — JARVIS listo"
