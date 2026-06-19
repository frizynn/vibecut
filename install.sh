#!/usr/bin/env bash
# Instalador de Vibecut. Bajalo desde Releases y corré:  bash install.sh
# Instala lo que falte (uv, ffmpeg/git, pnpm), clona el proyecto y lo deja como app.
set -euo pipefail

DEST="${VIBECUT_DIR:-$HOME/vibecut}"
REPO="https://github.com/frizynn/vibecut"

say()  { printf '\033[36m▸\033[0m %s\n' "$1"; }
ok()   { printf '\033[32m✓\033[0m %s\n' "$1"; }
warn() { printf '\033[33m! %s\033[0m\n' "$1"; }
have() { command -v "$1" >/dev/null 2>&1; }

# --- uv (instalador oficial, sin sudo) ---
if ! have uv; then
  say "Instalando uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1 || true
  export PATH="$HOME/.local/bin:$PATH"
fi
have uv && ok "uv" || warn "No pude instalar uv — instalalo de https://docs.astral.sh/uv/"

# --- git + ffmpeg (por gestor de paquetes del sistema, pide sudo) ---
missing_pkgs=""
have git || missing_pkgs="$missing_pkgs git"
have ffmpeg || missing_pkgs="$missing_pkgs ffmpeg"
if [ -n "$missing_pkgs" ]; then
  say "Instalando:$missing_pkgs (puede pedir tu contraseña)..."
  if   have apt-get; then sudo apt-get update -qq && sudo apt-get install -y $missing_pkgs
  elif have dnf;     then sudo dnf install -y $missing_pkgs
  elif have pacman;  then sudo pacman -S --noconfirm $missing_pkgs
  elif have brew;    then brew install $missing_pkgs
  else warn "Instalá a mano:$missing_pkgs"; fi
fi
have git    && ok "git"    || warn "Falta git"
have ffmpeg && ok "ffmpeg" || warn "Falta ffmpeg"

# --- node + pnpm ---
if ! have node; then
  warn "Falta Node.js. Instalalo desde https://nodejs.org/ (o con nvm) y volvé a correr esto."
  exit 1
fi
if ! have pnpm; then
  say "Instalando pnpm..."
  corepack enable >/dev/null 2>&1 && corepack prepare pnpm@latest --activate >/dev/null 2>&1 || npm i -g pnpm >/dev/null 2>&1 || true
fi
have pnpm && ok "pnpm" || { warn "No pude instalar pnpm — https://pnpm.io/installation"; exit 1; }

# --- clonar / actualizar ---
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
printf '  Para el copiloto: tené Claude Code (`claude`) o Codex (`codex login`) — usa tu suscripción, sin API key.\n'
