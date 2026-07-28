// Callback OAuth de Google. Recibe ?code y ?state, valida state, intercambia
// code por tokens, actualiza YT_REFRESH_TOKEN en GitHub Secrets y notifica
// por Telegram.

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
  const clientId = process.env.YT_CLIENT_ID;
  const clientSecret = process.env.YT_CLIENT_SECRET;
  const ghToken = process.env.GITHUB_DISPATCH_TOKEN;
  const ghOwner = process.env.GITHUB_OWNER;
  const ghRepo = process.env.GITHUB_REPO;

  if (!stateSecret || !clientId || !clientSecret || !ghToken || !ghOwner || !ghRepo) {
    return res.status(500).send(renderResult(
      "Configuración incompleta",
      "Faltan env vars en Vercel: revisa YT_CLIENT_ID, YT_CLIENT_SECRET, STATE_SECRET, GITHUB_DISPATCH_TOKEN.",
      false,
    ));
  }

  const err = req.query.error;
  if (err) {
    return res.status(200).send(renderResult(
      "Autorización cancelada",
      `Google devolvió el error: <code>${String(err).slice(0, 60)}</code>. Prueba el link de nuevo.`,
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
      "Google no devolvió un code de autorización.",
      false,
    ));
  }

  // Reconstruir redirect_uri exactamente igual (Google es estricto)
  const host = req.headers["x-forwarded-host"] || req.headers.host;
  const proto = req.headers["x-forwarded-proto"] || "https";
  const redirectUri = `${proto}://${host}/api/yt-auth-callback`;

  // Intercambiar code por tokens
  const tokenResp = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      code,
      client_id: clientId,
      client_secret: clientSecret,
      redirect_uri: redirectUri,
      grant_type: "authorization_code",
    }),
  });

  const tokenBody = await tokenResp.json();
  if (!tokenResp.ok || !tokenBody.refresh_token) {
    const detail = tokenBody.error_description || tokenBody.error || "unknown";
    return res.status(500).send(renderResult(
      "Google rechazó el intercambio",
      `Detalle: <code>${String(detail).slice(0, 200)}</code>. Puede ser que Google no devolviera refresh_token (asegúrate de revocar acceso previo en myaccount.google.com/permissions y probar de nuevo).`,
      false,
    ));
  }

  // Actualizar YT_REFRESH_TOKEN en GitHub Secrets
  try {
    await updateRepoSecret({
      owner: ghOwner,
      repo: ghRepo,
      secretName: "YT_REFRESH_TOKEN",
      value: tokenBody.refresh_token,
      token: ghToken,
    });
  } catch (e) {
    await tgSend(stateData.chat_id,
      `❌ <b>Reauth YT: fallo al guardar en GitHub</b>\n${String(e.message).slice(0, 200)}`);
    return res.status(500).send(renderResult(
      "Fallo al guardar en GitHub",
      `El PAT quizás no tiene scope <code>secrets:write</code>. Detalle: <code>${String(e.message).slice(0, 200)}</code>`,
      false,
    ));
  }

  // Notificar por Telegram
  await tgSend(stateData.chat_id,
    "✅ <b>Token YT renovado con éxito</b>\n\n" +
    "GitHub Secret <code>YT_REFRESH_TOKEN</code> actualizado. " +
    "El próximo Action leerá el token nuevo automáticamente. Ya no tienes " +
    "que tocar nada — hasta la próxima expiración (~7 días)."
  );

  return res.status(200).send(renderResult(
    "Token renovado",
    "El bot ya tiene el nuevo token. Los próximos videos se subirán con normalidad.",
    true,
  ));
}
