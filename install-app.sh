#!/usr/bin/env bash
# Instala Kimu como una app del menú (clickeable). Ejecutalo una sola vez.
set -euo pipefail
cd "$(dirname "$0")"
REPO="$(pwd)"

chmod +x start.sh

ICON="$REPO/public/favicon.png"
APPS_DIR="$HOME/.local/share/applications"
mkdir -p "$APPS_DIR"

cat > "$APPS_DIR/kimu.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Kimu
Comment=Editor de video con IA (local)
Exec=$REPO/start.sh
Icon=$ICON
Terminal=true
Categories=AudioVideo;Video;
EOF

chmod +x "$APPS_DIR/kimu.desktop"
update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true

printf '\033[32m✓ Listo.\033[0m Buscá "Kimu" en tu menú de aplicaciones y abrilo como cualquier app.\n'
printf '  (O corré ./start.sh desde la terminal.)\n'
