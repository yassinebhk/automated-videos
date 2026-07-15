// Vercel Function — recibe webhooks de Telegram y dispara GitHub Actions.
//
// Endpoint: POST /api/telegram
// Configuración: `setWebhook` a esta URL (una vez, ver README).
//
// Flujo:
//   1. Telegram envía un Update JSON al POST.
//   2. Extraemos `message.text` (formato "/comando args...") y `chat.id`.
//   3. Verificamos que el chat.id coincide con AUTHORIZED_CHAT_ID.
//   4. Hacemos POST a github.com/repos/OWNER/REPO/dispatches con event_type=
//      "telegram-command" y client_payload={cmd, args}.
//   5. Respondemos 200 a Telegram inmediato (< 10s idealmente; Actions se
//      dispara en background). Si tardamos, Telegram reintenta.
//
// Env vars (Vercel Project Settings → Environment Variables):
//   GITHUB_OWNER            — usuario/org (ej. "yassinebouhaik")
//   GITHUB_REPO             — nombre repo (ej. "automated-videos")
//   GITHUB_DISPATCH_TOKEN   — PAT con scope `repo` (dispatch permitido)
//   AUTHORIZED_CHAT_ID      — tu chat_id (ej. "8228932051") — rechaza otros
//   TELEGRAM_BOT_TOKEN      — para responder inmediato al usuario ("recibido…")

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ error: "POST only" });

  const update = req.body;
  const msg = update?.message ?? update?.edited_message;
  if (!msg?.text) return res.status(200).json({ ok: true, skipped: "no text" });

  const chatId = String(msg.chat?.id ?? "");
  if (chatId !== process.env.AUTHORIZED_CHAT_ID) {
    // No devolvemos 401 para no dar señales a scanners; 200 silencioso.
    return res.status(200).json({ ok: true, skipped: "unauthorized chat" });
  }

  const text = msg.text.trim();
  // Solo procesamos comandos (empiezan con /)
  if (!text.startsWith("/")) {
    return res.status(200).json({ ok: true, skipped: "no command" });
  }

  // Parse "/comando args resto..."
  const [rawCmd, ...rest] = text.slice(1).split(/\s+/);
  // Strip @botname suffix si el user tecleó "/autogen@mybot"
  const cmd = rawCmd.split("@")[0].toLowerCase();
  const args = rest.join(" ");

  const allowed = new Set([
    "autogen", "longgen", "snapshot", "atomize", "send",
    "ideas", "stats", "help", "start",
  ]);
  if (!allowed.has(cmd)) {
    await tgReply(chatId, `❌ Comando /${cmd} no soportado por el webhook.`);
    return res.status(200).json({ ok: true, skipped: "unknown command" });
  }

  // Dispatch a GitHub Actions
  const dispatchUrl = `https://api.github.com/repos/${process.env.GITHUB_OWNER}/${process.env.GITHUB_REPO}/dispatches`;
  const ghResp = await fetch(dispatchUrl, {
    method: "POST",
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${process.env.GITHUB_DISPATCH_TOKEN}`,
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      event_type: "telegram-command",
      client_payload: { cmd, args },
    }),
  });

  if (!ghResp.ok) {
    const errBody = await ghResp.text();
    await tgReply(chatId, `❌ GitHub dispatch falló (${ghResp.status}): ${errBody.slice(0, 200)}`);
    return res.status(200).json({ ok: false, gh_status: ghResp.status });
  }

  await tgReply(chatId, `⚙️ /${cmd} lanzado en GitHub Actions — te aviso cuando termine.`);
  return res.status(200).json({ ok: true, dispatched: cmd });
}

async function tgReply(chatId, text) {
  const url = `https://api.telegram.org/bot${process.env.TELEGRAM_BOT_TOKEN}/sendMessage`;
  try {
    await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: chatId, text }),
    });
  } catch (_) {
    // Silencioso — no queremos que un fallo de Telegram tumbe el 200 al webhook.
  }
}
