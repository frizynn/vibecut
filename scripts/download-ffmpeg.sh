#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

say() { printf '\033[36m▸\033[0m %s\n' "$1"; }

mkdir -p resources

FFMPEG=$(which ffmpeg 2>/dev/null || true)
FFPROBE=$(which ffprobe 2>/dev/null || true)

if [ -z "$FFMPEG" ] || [ -z "$FFPROBE" ]; then
  say "ERROR: ffmpeg/ffprobe no encontrados. Instalá con: brew install ffmpeg"
  exit 1
fi

say "Copiando ffmpeg de $FFMPEG a resources/ffmpeg..."
cp "$FFMPEG" resources/ffmpeg
chmod +x resources/ffmpeg

say "Copiando ffprobe de $FFPROBE a resources/ffprobe..."
cp "$FFPROBE" resources/ffprobe
chmod +x resources/ffprobe

say "✓ FFmpeg y FFprobe bundleados"
