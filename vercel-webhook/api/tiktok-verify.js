// Sirve el archivo de verificación de dominio TikTok al path
// /tiktokVa82lakWs7jaMizQqtDc5w1bzy3MdGEH.txt via rewrite en vercel.json.

export default function handler(req, res) {
  res.setHeader("Content-Type", "text/plain; charset=utf-8");
  res.setHeader("Cache-Control", "public, max-age=3600");
  res.status(200).send("tiktok-developers-site-verification=Va82lakWs7jaMizQqtDc5w1bzy3MdGEH\n");
}
