#!/usr/bin/env bash
# Bundles a standalone Python interpreter + all backend dependencies into
# resources/python/ and resources/python-site-packages/ for the macOS .dmg.
set -euo pipefail
cd "$(dirname "$0")/.."

export UV_INDEX_URL=https://pypi.org/simple/

say() { printf '\033[36m▸\033[0m %s\n' "$1"; }

say "Buscando Python 3.12 standalone de uv..."
PYTHON_BIN=$(uv python find 3.12 2>/dev/null || true)

if [ -z "$PYTHON_BIN" ]; then
  say "Instalando Python 3.12 con uv..."
  uv python install 3.12
  PYTHON_BIN=$(uv python find 3.12)
fi

PYTHON_DIR="$(dirname "$(dirname "$PYTHON_BIN")")"
say "Python standalone en: $PYTHON_DIR"

say "Copiando Python standalone a resources/python/..."
rm -rf resources/python
mkdir -p resources
cp -r "$PYTHON_DIR" resources/python

say "Instalando dependencias del backend en resources/python-site-packages/..."
rm -rf resources/python-site-packages
mkdir -p resources/python-site-packages
"$PYTHON_BIN" -m pip install \
  --target resources/python-site-packages \
  --index-url https://pypi.org/simple/ \
  aiosqlite \
  asyncpg \
  "fastapi[standard]" \
  "google-genai" \
  python-dotenv \
  python-multipart \
  "faster-whisper>=1.1.0" \
  uvicorn \
  uvloop

say "✓ Python bundle listo"
