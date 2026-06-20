#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

export npm_config_registry=https://registry.npmjs.org/
export COREPACK_ENABLE_STRICT=0
export PATH="/opt/homebrew/bin:$PATH"

say() { printf '\033[36m▸\033[0m %s\n' "$1"; }

say "Compilando videorender.ts con esbuild..."
mkdir -p dist

node_modules/.pnpm/node_modules/.bin/esbuild \
  app/videorender/videorender.ts \
  --bundle \
  --platform=node \
  --target=node20 \
  --format=esm \
  --tsconfig=tsconfig.json \
  --external:better-sqlite3 \
  --external:fsevents \
  --external:'@remotion/*' \
  --external:remotion \
  --outfile=dist/videorender.bundle.mjs

say "✓ Renderer compilado en dist/videorender.bundle.mjs"
