#!/usr/bin/env bash
# Kimu — lanzador único. Arranca todo y abre la app en una ventana.
# Primera vez: instala dependencias solo. Cerrá la ventana o Ctrl-C para salir.
set -euo pipefail
cd "$(dirname "$0")"

APP_URL="http://localhost:5173"
COMPOSE="docker compose -f docker-compose.dev.yml -f docker-compose.local.yml"

say() { printf '\033[36m▸\033[0m %s\n' "$1"; }
die() { printf '\033[31m✗ %s\033[0m\n' "$1" >&2; exit 1; }

say "Verificando herramientas..."
for bin in docker pnpm uv; do
  command -v "$bin" >/dev/null 2>&1 || die "Falta '$bin'. Instalalo y volvé a intentar."
done

if [ ! -f .env ]; then
  say "Creando configuración inicial (.env)..."
  cp .env.example .env
  sed -i.bak "s|^BETTER_AUTH_SECRET=.*|BETTER_AUTH_SECRET=$(openssl rand -hex 32)|" .env && rm -f .env.bak
fi

say "Iniciando base de datos..."
$COMPOSE up -d >/dev/null
until docker exec videoeditor-postgres-dev pg_isready -U videoeditor >/dev/null 2>&1; do sleep 1; done

if [ ! -d node_modules ]; then
  say "Instalando dependencias (solo la primera vez, puede tardar)..."
  pnpm install
fi
if [ ! -d backend/.venv ]; then
  say "Instalando dependencias del motor (solo la primera vez)..."
  (cd backend && uv sync)
fi

pids=()
cleanup() {
  printf '\n'; say "Cerrando Kimu..."
  for pid in "${pids[@]}"; do kill "$pid" 2>/dev/null || true; done
  $COMPOSE stop >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

say "Arrancando la app..."
( cd backend && uv run uvicorn main:app --port 3000 ) >/tmp/kimu-backend.log 2>&1 & pids+=($!)
pnpm dlx tsx app/videorender/videorender.ts >/tmp/kimu-renderer.log 2>&1 & pids+=($!)
pnpm dev >/tmp/kimu-frontend.log 2>&1 & pids+=($!)

# Abrir la ventana de la app cuando el editor esté listo.
open_app() {
  for _ in $(seq 1 60); do
    if curl -fsS -o /dev/null "$APP_URL" 2>/dev/null; then
      if command -v google-chrome >/dev/null 2>&1; then google-chrome --app="$APP_URL" >/dev/null 2>&1 &
      elif command -v chromium >/dev/null 2>&1; then chromium --app="$APP_URL" >/dev/null 2>&1 &
      elif command -v brave-browser >/dev/null 2>&1; then brave-browser --app="$APP_URL" >/dev/null 2>&1 &
      elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$APP_URL" >/dev/null 2>&1 &
      fi
      return
    fi
    sleep 1
  done
}
open_app &

printf '\n\033[32m  ✓ Kimu está abierto.\033[0m  Si la ventana no apareció, entrá a %s\n' "$APP_URL"
printf '    (Cerrá esta terminal o Ctrl-C para apagar todo.)\n\n'
wait
