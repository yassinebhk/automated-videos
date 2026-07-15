#!/usr/bin/env bash
# Despliega videogen a la VM desde la Mac. Uso:
#   bash deploy/push.sh <IP_PUBLICA> <ruta-al-ssh-key.key>
# Copia el código + .env + secrets, instala todo y arranca el servicio.
set -euo pipefail

IP="${1:?Falta IP pública de la VM}"
KEY="${2:?Falta ruta al SSH key}"
USER="${SSH_USER:-ubuntu}"
REMOTE="$USER@$IP"
SSH="ssh -i $KEY -o StrictHostKeyChecking=accept-new $REMOTE"

echo "==> Copiando código (rsync, sin .venv/output)…"
rsync -az --delete \
  --exclude '.venv' --exclude 'output' --exclude '__pycache__' \
  --exclude '*.pyc' --exclude '.git' \
  -e "ssh -i $KEY -o StrictHostKeyChecking=accept-new" \
  ./ "$REMOTE:~/automated-videos/"

echo "==> Copiando secretos (.env + OAuth)…"
$SSH "mkdir -p ~/automated-videos/secrets"
scp -i "$KEY" .env "$REMOTE:~/automated-videos/.env"
scp -i "$KEY" secrets/youtube_client_secret.json "$REMOTE:~/automated-videos/secrets/" 2>/dev/null || true
scp -i "$KEY" secrets/youtube_token.json "$REMOTE:~/automated-videos/secrets/" 2>/dev/null || true

echo "==> Ejecutando setup en la VM…"
$SSH "cd ~/automated-videos && bash deploy/setup.sh"

echo "==> Instalando servicio systemd del bot…"
$SSH "sudo cp ~/automated-videos/deploy/videogen-bot.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now videogen-bot && sleep 2 && sudo systemctl status videogen-bot --no-pager | head -8"

echo "✅ Desplegado. El bot corre 24/7 en la VM (sobrevive reinicios)."
