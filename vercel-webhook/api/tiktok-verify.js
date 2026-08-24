// Sirve DINÁMICAMENTE cualquier archivo de verificación TikTok.
// TikTok pide un archivo con nombre tiktok<TOKEN>.txt cuyo contenido debe
// ser tiktok-developers-site-verification=<TOKEN>. Como TikTok rota el
// token cada intento, extraemos el token del propio path solicitado y
// respondemos con el contenido correcto. Sin necesidad de redeploy.

export default function handler(req, res) {
  // El path llega como /tiktok<TOKEN>.txt (via rewrite en vercel.json)
  const url = String(req.url || "");
  const match = url.match(/tiktok([A-Za-z0-9_-]+)\.txt/);
  if (!match) {
    res.setHeader("Content-Type", "text/plain; charset=utf-8");
    return res.status(404).send("Not found");
  }
  const token = match[1];
  res.setHeader("Content-Type", "text/plain; charset=utf-8");
  res.setHeader("Cache-Control", "no-store, max-age=0, must-revalidate");
  res.setHeader("CDN-Cache-Control", "no-store");
  res.setHeader("Vercel-CDN-Cache-Control", "no-store");
  res.status(200).send(`tiktok-developers-site-verification=${token}\n`);
}
