#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Ensure public registries and Homebrew pnpm on PATH (macOS)
export npm_config_registry=https://registry.npmjs.org/
export COREPACK_ENABLE_STRICT=0
export UV_INDEX_URL=https://pypi.org/simple/
export PATH="/opt/homebrew/bin:$PATH"

say() { printf '\033[36m▸\033[0m %s\n' "$1"; }

say "=== Build Vibecut macOS ==="

say "1. Instalando dependencias npm (dev + prod)..."
pnpm install

say "2. Instalando dependencias del backend Python..."
(cd backend && uv sync)

say "3. Building React Router SSR frontend..."
pnpm build

say "4. Compilando renderer (videorender.ts → dist/videorender.bundle.mjs)..."
bash scripts/build-renderer.sh

say "5. Bundleando Python standalone + site-packages..."
bash scripts/build-python-bundle.sh

say "6. Copiando ffmpeg y ffprobe del sistema..."
bash scripts/download-ffmpeg.sh

say "7. Creando node_modules de runtime (flat, para el .dmg)..."
# pnpm's virtual store uses symlinks that don't survive electron-builder packaging.
# We create a flat installation (--shamefully-hoist) so all packages resolve correctly.
rm -rf runtime-node-modules
mkdir -p runtime-node-modules
cp package.json pnpm-lock.yaml runtime-node-modules/
(
  cd runtime-node-modules
  pnpm install --prod --shamefully-hoist --ignore-scripts
)
# Recompile better-sqlite3 against Electron's Node ABI
ELECTRON_VERSION=$(node -e "const e=require('./node_modules/electron/package.json');console.log(e.version)")
node_modules/.pnpm/node_modules/.bin/electron-rebuild \
  --module-dir runtime-node-modules \
  --version "$ELECTRON_VERSION" \
  2>&1 || say "⚠ electron-rebuild failed (non-fatal, continuing)"

say "8. Preparando ícono de la app (512x512)..."
mkdir -p electron-assets
sips -z 512 512 public/favicon.png --out electron-assets/icon.png > /dev/null

say "9. Compilando Electron main process..."
bash scripts/build-electron-main.sh

say "10. Empaquetando .dmg con electron-builder..."
pnpm exec electron-builder --mac

say "=== ✓ Build completo. DMG en dist-electron/ ==="
