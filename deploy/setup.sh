#!/usr/bin/env bash
# Setup de videogen en una VM Ubuntu (Oracle Cloud Always Free, ARM o x86).
# Se ejecuta EN la VM, después de copiar el código a ~/automated-videos.
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/automated-videos}"

echo "==> 0/6 Zona horaria → Europe/Madrid (para que slots y resumen diario casen con tu hora)"
sudo timedatectl set-timezone Europe/Madrid 2>/dev/null || sudo ln -sf /usr/share/zoneinfo/Europe/Madrid /etc/localtime
date

echo "==> 1/6 Paquetes del sistema (ffmpeg con libass, python, etc.)"
sudo apt-get update -y
sudo apt-get install -y ffmpeg python3-venv python3-pip fonts-dejavu-core curl
if ! ffmpeg -hide_banner -filters 2>/dev/null | grep -q "^ T.. ass "; then
  echo "⚠️  ffmpeg parece no traer libass — los subtítulos quemados pueden fallar"
fi

echo "==> 2/6 Entorno virtual + dependencias"
cd "$APP_DIR"
python3 -m venv .venv
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -e .

echo "==> 3/6 Fuente Montserrat"
mkdir -p assets/fonts
if [ ! -f assets/fonts/Montserrat.ttf ]; then
  curl -sSL -o assets/fonts/Montserrat.ttf \
    "https://raw.githubusercontent.com/google/fonts/main/ofl/montserrat/Montserrat%5Bwght%5D.ttf"
fi

echo "==> 4/6 Música royalty-free (fallback Incompetech CC-BY si no se rsync-eó)"
mkdir -p music/epic music/chill music/mystery music/upbeat
dl() { [ -f "$2" ] || curl -sSL --max-time 60 -o "$2" "$1" || true; }
[ "$(ls music/epic 2>/dev/null | wc -l)" -gt 0 ] || dl "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Inspired.mp3" music/epic/inspired.mp3
[ "$(ls music/chill 2>/dev/null | wc -l)" -gt 0 ] || dl "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Carefree.mp3" music/chill/carefree.mp3
[ "$(ls music/mystery 2>/dev/null | wc -l)" -gt 0 ] || dl "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Sneaky%20Snitch.mp3" music/mystery/sneaky-snitch.mp3
[ "$(ls music/upbeat 2>/dev/null | wc -l)" -gt 0 ] || dl "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Wallpaper.mp3" music/upbeat/wallpaper.mp3
echo "  moods con audio:" $(ls music/ 2>/dev/null | xargs -n1 -I{} sh -c '[ "$(ls music/{} 2>/dev/null | wc -l)" -gt 0 ] && echo {}' | tr '\n' ' ')

echo "==> 5/6 Carpetas de trabajo"
mkdir -p output/pending_review output/uploaded

echo "==> 6/6 Verificación"
./.venv/bin/videogen doctor || true

echo ""
echo "✅ Setup completo. Falta:"
echo "   • Copiar tu .env y secrets/youtube_client_secret.json + youtube_token.json"
echo "   • Instalar el servicio: sudo cp deploy/videogen-bot.service /etc/systemd/system/ && sudo systemctl enable --now videogen-bot"
