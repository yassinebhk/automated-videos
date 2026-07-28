// Inicia el flow OAuth con Google. Redirige al usuario a la pantalla de
// autorización de Google. Cuando Google acepte, redirige a /api/yt-auth-callback.
//
// Uso: se accede desde el botón inline de Telegram (o directo desde el móvil).
// La URL incluye ?t=<TOKEN> firmado con STATE_SECRET para evitar que un
// desconocido inicie el flow (auth previa).
//
// Env vars requeridas en Vercel:
//   YT_CLIENT_ID      - de tu OAuth Client Google (mismo del pipeline)
//   STATE_SECRET      - random 32 bytes hex (yo genero uno al deploy)
//   VERCEL_URL        - auto-set por Vercel (o VERCEL_BRANCH_URL)

import crypto from "node:crypto";

const SCOPES = [
  "https://www.googleapis.com/auth/youtube.upload",
  "https://www.googleapis.com/auth/youtube.readonly",
  "https://www.googleapis.com/auth/youtube.force-ssl",
];

function signState(payload, secret) {
  const body = Buffer.from(JSON.stringify(payload)).toString("base64url");
  const sig = crypto.createHmac("sha256", secret).update(body).digest("base64url");
  return `${body}.${sig}`;
}

export default function handler(req, res) {
  const clientId = process.env.YT_CLIENT_ID;
  const stateSecret = process.env.STATE_SECRET;
  if (!clientId || !stateSecret) {
    return res.status(500).json({ error: "missing YT_CLIENT_ID or STATE_SECRET env" });
  }

  // Autorización previa: la URL trae ?t=<AUTHORIZED_CHAT_ID> — verifica sea el
  // chat autorizado del user (evita que alguien random inicie el flow).
  const providedT = String(req.query.t || "");
  const authorizedChat = String(process.env.AUTHORIZED_CHAT_ID || "");
  if (!providedT || providedT !== authorizedChat) {
    return res.status(403).json({
      error: "not authorized",
      hint: "usa el enlace que envió el bot",
    });
  }

  // Redirect URI: absoluto al mismo dominio
  const host = req.headers["x-forwarded-host"] || req.headers.host;
  const proto = req.headers["x-forwarded-proto"] || "https";
  const redirectUri = `${proto}://${host}/api/yt-auth-callback`;

  // State para prevenir CSRF + carry del chat_id (info)
  const state = signState(
    { chat_id: authorizedChat, ts: Date.now() },
    stateSecret,
  );

  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: redirectUri,
    response_type: "code",
    scope: SCOPES.join(" "),
    access_type: "offline",
    prompt: "consent",  // fuerza que Google devuelva refresh_token siempre
    state,
  });

  return res.redirect(302, `https://accounts.google.com/o/oauth2/v2/auth?${params}`);
}
