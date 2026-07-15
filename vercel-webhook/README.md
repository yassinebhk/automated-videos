# videogen — Telegram webhook (Vercel)

Función serverless que recibe `POST` de Telegram y dispara GitHub Actions vía `repository_dispatch`.

## Deploy (una vez)

```bash
cd vercel-webhook
npx vercel deploy --prod
```

Anota la URL final, ejemplo: `https://videogen-webhook-abc.vercel.app`

## Variables de entorno (Vercel dashboard)

| Var | Valor |
|---|---|
| `GITHUB_OWNER` | `yassinebouhaik` (o tu username exacto) |
| `GITHUB_REPO` | `automated-videos` |
| `GITHUB_DISPATCH_TOKEN` | PAT con scope `repo` (fine-grained OK con "Contents: read+write" + "Metadata: read") |
| `AUTHORIZED_CHAT_ID` | Tu chat_id de Telegram (evita que rando abuse) |
| `TELEGRAM_BOT_TOKEN` | Token del bot |

## Registrar webhook en Telegram (una vez)

```bash
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -d "url=https://<vercel-url>/api/telegram" \
  -d "allowed_updates=[\"message\",\"edited_message\"]"
```

Verificar:

```bash
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

## Comandos soportados

- `/autogen` — genera + programa Short del día
- `/longgen` — long-form semanal + atomiza
- `/snapshot` — snapshot stats + charts
- `/atomize <slug>` — atomiza un long existente
- `/send <slug>` — reenvía versión sin subs para TT/IG
- `/ideas` — genera ideas true crime
- `/stats` — foto rápida del canal
- `/help` — lista

Todo lo demás → mensaje "no soportado".

## ¿Y el long-polling del bot Mac?

Si el bot Mac sigue vivo, competirá con el webhook (409 conflict — solo puede haber uno). Antes de setWebhook, matar el bot Mac con:

```bash
pkill -f "videogen bot"
```

Y quitar el `caffeinate` que lo mantenía vivo.
