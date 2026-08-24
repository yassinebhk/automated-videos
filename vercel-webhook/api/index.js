// Homepage con el meta tag de verificación TikTok. Servido en / via
// rewrite en vercel.json.

const HTML = `<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="tiktok-developers-site-verification" content="jYEtDCE0kptF8mhBRMkchQIWfrTDqXDr">
<title>WaitWhy Autopost</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 640px; margin: 4rem auto; padding: 1rem; line-height: 1.6; color: #222; text-align: center; }
  h1 { font-size: 2rem; }
  a { color: #2563eb; }
</style>
</head>
<body>
<h1>WaitWhy Autopost</h1>
<p>Personal automation service for cross-posting a single Spanish-language media channel's content across YouTube, Instagram, Threads, TikTok, Bluesky, and Mastodon.</p>
<p><a href="/legal/tos">Terms of Service</a> · <a href="/legal/privacy">Privacy Policy</a></p>
</body>
</html>`;

export default function handler(req, res) {
  res.setHeader("Content-Type", "text/html; charset=utf-8");
  // Vercel respeta CDN-Cache-Control y Vercel-CDN-Cache-Control por encima
  // del Cache-Control estándar. Todas a "no-store" para garantizar que el
  // verifier de TikTok siempre vea el meta tag vigente.
  res.setHeader("Cache-Control", "no-store, max-age=0, must-revalidate");
  res.setHeader("CDN-Cache-Control", "no-store");
  res.setHeader("Vercel-CDN-Cache-Control", "no-store");
  res.status(200).send(HTML);
}
