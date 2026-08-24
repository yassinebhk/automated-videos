// Callback OAuth de TikTok. Recibe ?code y ?state, valida state, intercambia
// code por access_token + refresh_token, guarda ambos + open_id en GitHub
// Secrets, y notifica por Telegram.

import crypto from "node:crypto";
import { updateRepoSecret } from "../lib/github-secret.js";

function verifyState(state, secret) {
  const [body, sig] = String(state || "").split(".");
  if (!body || !sig) return null;
  const expected = crypto.createHmac("sha256", secret).update(body).digest("base64url");
  if (
    !crypto.timingSafeEqual(
      Buffer.from(sig),
      Buffer.from(expected)
    )
  ) return null;
  try {
    return JSON.parse(Buffer.from(body, "base64url").toString());
  } catch {
    return null;
  }
}

async function tgSend(chatId, text) {
  const tok = process.env.TELEGRAM_BOT_TOKEN;
  if (!tok || !chatId) return;
  try {
    await fetch(`https://api.telegram.org/bot${tok}/sendMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: chatId, text, parse_mode: "HTML" }),
    });
  } catch {}
}

function renderResult(title, body, ok) {
  const color = ok ? "#16a34a" : "#dc2626";
  const icon = ok ? "✅" : "❌";
  return `<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${title}</title>
<style>
body{margin:0;font-family:-apple-system,system-ui,sans-serif;background:#f7f7f9;
     display:flex;align-items:center;justify-content:center;min-height:100vh;padding:20px}
.card{background:#fff;border-radius:18px;padding:32px;max-width:420px;text-align:center;
      box-shadow:0 8px 30px rgba(0,0,0,.08)}
.icon{font-size:56px;margin-bottom:8px}
h1{color:${color};margin:8px 0 12px;font-size:24px}
p{color:#4b5563;line-height:1.5;margin:0 0 16px}
small{color:#9ca3af}
</style></head><body>
<div class="card">
  <div class="icon">${icon}</div>
  <h1>${title}</h1>
  <p>${body}</p>
  <small>Puedes cerrar esta pestaña.</small>
</div></body></html>`;
}

export default async function handler(req, res) {
  const stateSecret = process.env.STATE_SECRET;
  const clientKey = process.env.TIKTOK_CLIENT_KEY;
  const clientSecret = process.env.TIKTOK_CLIENT_SECRET;
  const ghToken = process.env.GITHUB_DISPATCH_TOKEN;
  const ghOwner = process.env.GITHUB_OWNER;
  const ghRepo = process.env.GITHUB_REPO;

  if (!stateSecret || !clientKey || !clientSecret || !ghToken || !ghOwner || !ghRepo) {
    return res.status(500).send(renderResult(
      "Configuración incompleta",
      "Faltan env vars en Vercel: TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, STATE_SECRET o GITHUB_DISPATCH_TOKEN.",
      false,
    ));
  }

  const err = req.query.error;
  if (err) {
    return res.status(200).send(renderResult(
      "Autorización cancelada",
      `TikTok devolvió el error: <code>${String(err).slice(0, 100)}</code>. Prueba de nuevo.`,
      false,
    ));
  }

  const stateData = verifyState(req.query.state, stateSecret);
  if (!stateData) {
    return res.status(400).send(renderResult(
      "State inválido",
      "El link ha expirado o ha sido manipulado. Solicita uno nuevo desde el bot.",
      false,
    ));
  }

  const code = String(req.query.code || "");
  if (!code) {
    return res.status(400).send(renderResult(
      "Falta el código",
      "TikTok no devolvió un code de autorización.",
      false,
    ));
  }

  const host = req.headers["x-forwarded-host"] || req.headers.host;
  const proto = req.headers["x-forwarded-proto"] || "https";
  const redirectUri = `${proto}://${host}/api/tiktok-callback`;

  // Intercambiar code por tokens. TikTok endpoint distinto de Google.
  const tokenResp = await fetch("https://open.tiktokapis.com/v2/oauth/token/", {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      "Cache-Control": "no-cache",
    },
    body: new URLSearchParams({
      client_key: clientKey,
      client_secret: clientSecret,
      code,
      grant_type: "authorization_code",
      redirect_uri: redirectUri,
    }),
  });

  const tokenBody = await tokenResp.json();
  if (!tokenResp.ok || !tokenBody.access_token) {
    const detail = tokenBody.error_description || tokenBody.error || JSON.stringify(tokenBody).slice(0, 200);
    return res.status(500).send(renderResult(
      "TikTok rechazó el intercambio",
      `Detalle: <code>${String(detail).slice(0, 300)}</code>`,
      false,
    ));
  }

  const accessToken = tokenBody.access_token;
  const refreshToken = tokenBody.refresh_token || "";
  const openId = tokenBody.open_id || "";
  const grantedScopes = tokenBody.scope || "";

  // Guardar 3 secrets en GitHub
  try {
    await updateRepoSecret({ owner: ghOwner, repo: ghRepo,
      secretName: "TIKTOK_ACCESS_TOKEN", value: accessToken, token: ghToken });
    if (refreshToken) {
      await updateRepoSecret({ owner: ghOwner, repo: ghRepo,
        secretName: "TIKTOK_REFRESH_TOKEN", value: refreshToken, token: ghToken });
    }
    if (openId) {
      await updateRepoSecret({ owner: ghOwner, repo: ghRepo,
        secretName: "TIKTOK_OPEN_ID", value: openId, token: ghToken });
    }
  } catch (e) {
    await tgSend(stateData.chat_id,
      `❌ <b>TikTok auth: fallo al guardar secrets</b>\n${String(e.message).slice(0, 200)}`);
    return res.status(500).send(renderResult(
      "Fallo al guardar en GitHub",
      `El PAT quizás no tiene scope secrets:write. Detalle: <code>${String(e.message).slice(0, 200)}</code>`,
      false,
    ));
  }

  await tgSend(stateData.chat_id,
    "✅ <b>TikTok conectado</b>\n\n" +
    `Scopes activos: <code>${grantedScopes || "(none)"}</code>\n` +
    (grantedScopes.includes("video.publish")
      ? "🟢 Puedes publicar <b>directo</b> (auto-post activo).\n"
      : "🟡 Solo <code>video.upload</code> aprobado — videos irán a borradores hasta que TikTok apruebe review.\n") +
    "\nTokens guardados como <code>TIKTOK_ACCESS_TOKEN</code>, <code>TIKTOK_REFRESH_TOKEN</code>, <code>TIKTOK_OPEN_ID</code>."
  );

  return res.status(200).send(renderResult(
    "TikTok conectado",
    grantedScopes.includes("video.publish")
      ? "Publicación directa habilitada. Los próximos Shorts se subirán automáticamente a TikTok."
      : "Solo permiso de upload aprobado. Los videos irán a borradores; publica manualmente hasta que TikTok apruebe la solicitud de review.",
    true,
  ));
}
