// Inicia el flow OAuth con TikTok. Redirige al usuario a la pantalla de
// autorización. Cuando TikTok acepte, redirige a /api/tiktok-callback.
//
// Env vars requeridas en Vercel:
//   TIKTOK_CLIENT_KEY     - del app en developers.tiktok.com
//   STATE_SECRET          - random 32 bytes hex (reusa el mismo de YT)
//   AUTHORIZED_CHAT_ID    - para autorización previa via ?t=<chat_id>

import crypto from "node:crypto";

// user.info.basic  → obtener open_id + username (necesario para el poster)
// user.info.stats  → total likes/followers/videos (para daily summary)
// video.upload     → subir a bandeja de borradores (Sandbox, sin review)
// video.list       → leer views/likes/comments por video (para daily summary)
//
// video.publish se AÑADIRÁ AQUÍ una vez TikTok apruebe la review — hasta
// entonces, incluirlo en la petición hace que TikTok rechace la auth con
// "invalid_scope" porque el scope no está registrado en el app dashboard.
// video.publish: en Sandbox mode la cuenta del developer (waitwhy_/interest_stuff)
// puede publicar DIRECTO al feed sin review, saltándose el intermediate step
// de "inbox" que en Sandbox parece no exponer los videos en la UI.
const SCOPES = [
  "user.info.basic",
  "user.info.stats",
  "video.upload",
  "video.publish",
  "video.list",
];

function signState(payload, secret) {
  const body = Buffer.from(JSON.stringify(payload)).toString("base64url");
  const sig = crypto.createHmac("sha256", secret).update(body).digest("base64url");
  return `${body}.${sig}`;
}

export default function handler(req, res) {
  const clientKey = process.env.TIKTOK_CLIENT_KEY;
  const stateSecret = process.env.STATE_SECRET;
  if (!clientKey || !stateSecret) {
    return res.status(500).json({ error: "missing TIKTOK_CLIENT_KEY or STATE_SECRET env" });
  }

  const providedT = String(req.query.t || "");
  const authorizedChat = String(process.env.AUTHORIZED_CHAT_ID || "");
  if (!providedT || providedT !== authorizedChat) {
    return res.status(403).json({
      error: "not authorized",
      hint: "usa el enlace que envió el bot",
    });
  }

  const host = req.headers["x-forwarded-host"] || req.headers.host;
  const proto = req.headers["x-forwarded-proto"] || "https";
  const redirectUri = `${proto}://${host}/api/tiktok-callback`;

  const state = signState(
    { chat_id: authorizedChat, ts: Date.now() },
    stateSecret,
  );

  // TikTok usa client_key en vez de client_id, y scope comma-separated.
  const params = new URLSearchParams({
    client_key: clientKey,
    redirect_uri: redirectUri,
    response_type: "code",
    scope: SCOPES.join(","),
    state,
  });

  return res.redirect(302, `https://www.tiktok.com/v2/auth/authorize/?${params}`);
}
