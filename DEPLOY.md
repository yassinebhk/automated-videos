# Deploy 24/7 gratis para siempre — checklist

Refactor de bot long-polling → GitHub Actions (compute) + Vercel Function (webhook Telegram). Todo gratis para siempre en Hobby/Free tiers.

## Arquitectura

```
Telegram user ─▶ Vercel /api/telegram ─▶ github.com/dispatches ─▶ Actions
     ▲                                                              │
     └──────────────────  sendMessage/sendVideo ◀────────────────────┘

Cron GH Actions:
  daily-short         06:00 UTC (=08 CEST)   → autogen-once
  daily-summary       07:00 UTC (=09 CEST)   → daily-summary
  hourly-catchup      06-20 UTC (cada hora)  → hourly-catchup
  weekly-longform     dom 08:00 UTC          → longgen-once
  weekly-catchup      dom 10-22 + lun 10-14  → weekly-catchup

Concurrency group `videogen-generation` asegura 1 job a la vez (reemplaza el lock file del bot Mac).

Estado:
  output/stats_history.jsonl       → commit+push en cada run (append-only)
  secrets/youtube_token.json       → reconstruido desde GH Secrets en cada run
                                     (refresh_token + client_id + client_secret)
                                     No requiere persist-back porque google-auth
                                     regenera el access_token en cada refresh.
```

## Setup paso a paso

### 1. Crear repo público en GitHub

```bash
cd /Users/yassinebouhaikbouhoussaine/automated-videos
git init
git branch -M main
git add .
git commit -m "initial commit — videogen + Actions + webhook"

# Con gh CLI (recomendado)
gh repo create automated-videos --public --source=. --push

# O manualmente en github.com y luego:
# git remote add origin git@github.com:yassinebouhaik/automated-videos.git
# git push -u origin main
```

### 2. Configurar GitHub Secrets

En `github.com/yassinebouhaik/automated-videos/settings/secrets/actions`:

| Secret | Valor |
|---|---|
| `TELEGRAM_BOT_TOKEN` | (tu token) |
| `TELEGRAM_CHAT_ID` | `8228932051` |
| `GEMINI_API_KEY` | (tu key) |
| `PEXELS_API_KEY` | (tu key) |
| `YOUTUBE_CHANNEL_ID_ES` | (tu channel id) |
| `YOUTUBE_CHANNEL_ID_EN` | (tu channel id EN) |
| `YT_REFRESH_TOKEN` | Extraído de `secrets/youtube_token.json` — campo `refresh_token` |
| `YT_CLIENT_ID` | Extraído del mismo JSON o de tu proyecto Google Cloud |
| `YT_CLIENT_SECRET` | Extraído del mismo JSON o de tu proyecto Google Cloud |

Extraer valores:
```bash
python3 -c "import json; d=json.load(open('secrets/youtube_token.json')); \
  print('REFRESH:', d['refresh_token']); \
  print('CLIENT_ID:', d['client_id']); \
  print('CLIENT_SECRET:', d['client_secret'])"
```

### 3. Verificar workflows corren

En `github.com/yassinebouhaik/automated-videos/actions` → `Daily Short` → `Run workflow` (manual dispatch).
Si el smoke test pasa: sube un vídeo real. Si falla, mira los logs.

### 4. Deploy webhook a Vercel

```bash
cd vercel-webhook
npx vercel deploy --prod
```

Anotar URL final (ej. `https://videogen-webhook-abc.vercel.app`).

En Vercel Dashboard → tu proyecto → Environment Variables:

| Var | Valor |
|---|---|
| `GITHUB_OWNER` | `yassinebouhaik` |
| `GITHUB_REPO` | `automated-videos` |
| `GITHUB_DISPATCH_TOKEN` | PAT de GitHub con scope `repo` |
| `AUTHORIZED_CHAT_ID` | `8228932051` |
| `TELEGRAM_BOT_TOKEN` | (mismo token) |

Crear PAT: github.com/settings/tokens/new → Fine-grained → repository=automated-videos → Repository permissions: `Contents: Read+Write` + `Metadata: Read`. Copia el token.

Redeploy tras añadir env vars:
```bash
npx vercel deploy --prod
```

### 5. Cambiar Telegram de long-polling a webhook

**Antes de setWebhook, matar el bot Mac** (si sigue corriendo):

```bash
pkill -f "videogen bot"
# Verificar
pgrep -f "videogen bot" || echo "bot muerto"
```

Registrar webhook (una vez):

```bash
TOKEN=<tu_token>
URL=https://videogen-webhook-abc.vercel.app/api/telegram
curl -X POST "https://api.telegram.org/bot$TOKEN/setWebhook" \
  -d "url=$URL" \
  -d "allowed_updates=[\"message\",\"edited_message\"]"
```

Verificar:
```bash
curl "https://api.telegram.org/bot$TOKEN/getWebhookInfo"
```

### 6. Test end-to-end

Manda al bot:
- `/help` → responde inmediato desde webhook + dispara Action `dispatch --cmd help`
- `/snapshot` → dispara Action que hace snapshot analytics y devuelve a Telegram
- `/autogen` → dispara Action que genera + programa Short + notifica

En Actions UI se ve el run corriendo. En Telegram llegan los mensajes finales.

### 7. Volver al long-polling (rollback)

Si algo va mal:
```bash
# Quitar webhook
curl -X POST "https://api.telegram.org/bot$TOKEN/deleteWebhook"

# Relanzar bot Mac
cd /Users/yassinebouhaikbouhoussaine/automated-videos
nohup caffeinate -di .venv/bin/videogen bot > /tmp/videogen_bot.log 2>&1 &
```

## Costes reales

- **GitHub Actions**: repo público = ilimitado. Estimado: 250 min/mes usados.
- **Vercel Hobby**: 100K invocaciones/mes gratis. Estimado: 50-500 msgs/mes.
- **Telegram Bot API**: gratis siempre.
- **Total: 0€/mes garantizado para siempre.**

## Limits que podrían morder

- **Vercel Hobby function 60s timeout**: aquí OK, la function solo hace un dispatch (< 2s).
- **GitHub Actions concurrency**: en repos públicos hay ~20 jobs concurrentes máximo. Nuestro `concurrency: videogen-generation` fuerza cola → nunca más de 1 a la vez.
- **YouTube upload quota**: 10.000 units/día. Un upload = ~1600 units. Sobrado (~6 uploads/día máx real).
- **Gemini free tier**: 10 requests/min, 1500/día. Autogen consume ~15 requests → nada.
