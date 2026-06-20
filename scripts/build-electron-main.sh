#!/usr/bin/env bash
# Compiles electron/main.ts and electron/preload.ts using esbuild.
# Bundles express, @react-router/express, http-proxy-middleware into the main
# bundle so the packaged app doesn't need them in runtime node_modules.
set -euo pipefail
cd "$(dirname "$0")/.."

export npm_config_registry=https://registry.npmjs.org/
export COREPACK_ENABLE_STRICT=0
export PATH="/opt/homebrew/bin:$PATH"

say() { printf '\033[36m▸\033[0m %s\n' "$1"; }

say "Compilando electron/main.ts..."
mkdir -p dist/electron/main dist/electron/preload

node_modules/.pnpm/node_modules/.bin/esbuild \
  electron/main.ts \
  --bundle \
  --platform=node \
  --target=node20 \
  --format=cjs \
  --external:electron \
  --outfile=dist/electron/main/index.js

say "Compilando electron/preload.ts..."
node_modules/.pnpm/node_modules/.bin/esbuild \
  electron/preload.ts \
  --bundle \
  --platform=node \
  --target=node20 \
  --format=cjs \
  --external:electron \
  --outfile=dist/electron/preload/index.js

say "✓ Electron main process compilado en dist/electron/"
