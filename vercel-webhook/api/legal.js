// Sirve TOS + Privacy embed. Servido en /legal/tos y /legal/privacy via
// rewrites en vercel.json.

const TOS = `<!DOCTYPE html><html lang="es"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="tiktok-developers-site-verification" content="OmgJZY3V5Yu3nm0zofXPViJhSvYHyyKL">
<title>Terms of Service — WaitWhy Autopost</title>
<style>body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;max-width:720px;margin:2rem auto;padding:1rem;line-height:1.6;color:#222}h1{border-bottom:2px solid #333;padding-bottom:.5rem}h2{margin-top:2rem}code{background:#f4f4f4;padding:.1rem .3rem;border-radius:3px}</style>
</head><body>
<h1>Terms of Service — WaitWhy Autopost</h1>
<p><strong>Last updated:</strong> 2026-08-24</p>
<h2>1. Purpose</h2>
<p>WaitWhy Autopost is an automation tool that helps a single content creator publish their own video content across multiple platforms (YouTube, Instagram, Threads, Bluesky, Mastodon, TikTok). It is not offered as a service to third parties.</p>
<h2>2. Scope of Use</h2>
<p>The tool acts on behalf of the sole authorized user (the account owner). All content published is created by, or licensed to, the account owner. No third-party access or user data collection occurs.</p>
<h2>3. Content Ownership</h2>
<p>All content published through WaitWhy Autopost is owned by the account owner. Third-party assets (music, images) used in videos are sourced under permissive licenses (Creative Commons, Wikimedia Commons, royalty-free stock).</p>
<h2>4. TikTok Platform Compliance</h2>
<p>Videos posted to TikTok via this tool comply with TikTok Community Guidelines and applicable content policies. The tool does not scrape, extract, or redistribute TikTok user data.</p>
<h2>5. No Warranty</h2>
<p>This tool is provided "as is" for personal use, with no warranty of uptime or fitness for a particular purpose.</p>
<h2>6. Contact</h2>
<p>For questions regarding these terms, contact: <code>yassine.bouhaik [at] tupl.com</code></p>
</body></html>`;

const PRIVACY = `<!DOCTYPE html><html lang="es"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="tiktok-developers-site-verification" content="OmgJZY3V5Yu3nm0zofXPViJhSvYHyyKL">
<title>Privacy Policy — WaitWhy Autopost</title>
<style>body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;max-width:720px;margin:2rem auto;padding:1rem;line-height:1.6;color:#222}h1{border-bottom:2px solid #333;padding-bottom:.5rem}h2{margin-top:2rem}code{background:#f4f4f4;padding:.1rem .3rem;border-radius:3px}</style>
</head><body>
<h1>Privacy Policy — WaitWhy Autopost</h1>
<p><strong>Last updated:</strong> 2026-08-24</p>
<h2>1. Overview</h2>
<p>WaitWhy Autopost is a personal-use automation tool operated by a single account owner. It publishes the owner's own video content to multiple social platforms including TikTok, Instagram, Threads, YouTube, Bluesky and Mastodon.</p>
<h2>2. Data We Collect</h2>
<p>The tool does not collect data from any third party. It only handles the account owner's own:</p>
<ul>
<li>OAuth access and refresh tokens (stored as encrypted GitHub Actions Secrets)</li>
<li>User ID and username of the owner's own social accounts</li>
<li>Video files created by the account owner</li>
</ul>
<h2>3. Data We Do Not Collect</h2>
<p>The tool does not collect, process, or store any information about TikTok users, viewers, followers, or any third parties. It does not access, analyze, or export video engagement data of others.</p>
<h2>4. Data Sharing</h2>
<p>No data is shared with any third party. Videos are posted directly from a GitHub Actions runner to the TikTok Content Posting API endpoints.</p>
<h2>5. Data Retention</h2>
<p>OAuth tokens are stored encrypted in GitHub Actions Secrets and rotated periodically. Video files are transmitted directly to TikTok via the Content Posting API's FILE_UPLOAD chunked HTTP flow. No user data is retained.</p>
<h2>6. Deletion Requests</h2>
<p>As no third-party data is collected, no deletion process applies. To revoke tool access, the account owner can revoke the app authorization in TikTok's developer settings at any time.</p>
<h2>7. Contact</h2>
<p>For privacy inquiries, contact: <code>yassine.bouhaik [at] tupl.com</code></p>
</body></html>`;

export default function handler(req, res) {
  const url = String(req.url || "");
  const page = url.includes("privacy") ? PRIVACY : TOS;
  res.setHeader("Content-Type", "text/html; charset=utf-8");
  res.setHeader("Cache-Control", "public, max-age=3600");
  res.status(200).send(page);
}
