#!/usr/bin/env bash
# Instalador de Vibecut. Descargá este archivo desde Releases y corré:
#   bash install.sh
# Clona el proyecto y lo deja como app del menú. Reqs: git, node+pnpm, uv, ffmpeg.
set -euo pipefail

DEST="${VIBECUT_DIR:-$HOME/vibecut}"
REPO="https://github.com/frizynn/vibecut"

say() { printf '\033[36m▸\033[0m %s\n' "$1"; }
warn() { printf '\033[33m! %s\033[0m\n' "$1"; }

say "Verificando herramientas necesarias..."
missing=""
for bin in git pnpm uv ffmpeg; do
  command -v "$bin" >/dev/null 2>&1 || missing="$missing $bin"
done
if [ -n "$missing" ]; then
  warn "Faltan estas herramientas:$missing"
  echo "  Instalalas una vez:"
  echo "    - Node.js + pnpm : https://pnpm.io/installation"
  echo "    - uv             : https://docs.astral.sh/uv/"
  echo "    - ffmpeg / git   : sudo apt install ffmpeg git   (Ubuntu/Debian)"
  exit 1
fi

if [ -d "$DEST/.git" ]; then
  say "Actualizando Vibecut en $DEST ..."
  git -C "$DEST" pull --ff-only
else
  say "Descargando Vibecut en $DEST ..."
  git clone --depth 1 "$REPO" "$DEST"
fi

cd "$DEST"
./install-app.sh

printf '\n\033[32m✓ Vibecut instalado.\033[0m Buscá "Vibecut" en el menú de aplicaciones,\n'
printf '  o corré: %s/start.sh\n' "$DEST"
