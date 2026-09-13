"""Auto-retry de workflows GH Actions que fallaron recientemente.

Cada hora escanea runs con conclusion=failure de los últimos 60 min y
los relanza automáticamente 1 vez más. Cubre glitches transitorios:
  - Timeouts API (Gemini, Pixabay, Pollinations)
  - Rate limits temporales
  - Network flaps del runner GH

NO reintenta:
  - Runs ya re-ejecutados (attempt > 1) — evita loops infinitos
  - Errores estructurales conocidos (invalid_client, no secrets)
  - Workflows de mantenimiento (healthcheck, ypp-watch, etc.)

Requiere: REPO_ADMIN_PAT con scope actions:write (ya existe).
"""
from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone, timedelta

REPO = "yassinebhk/automated-videos"
GH_API = "https://api.github.com"

# Workflows que NO se re-intentan (mantenimiento / ya reintentan solos)
SKIP_WORKFLOWS = {
    "Health-check ecosistema (cada 6h)",
    "YPP watch (semanal — distancia monetización)",
    "Auto-retry workflows failed",  # el propio, no se re-ejecuta
    "Hourly catchup (short)",  # ya es su propio catchup
    "pages build and deployment",
    "First-comment catchup (post author comment on public videos)",
    "Bluesky growth loop",  # cada 6h por su cuenta
    "Mastodon growth loop",
    "X growth loop (follows + likes ES)",
    "Meta Token Refresh",
    "TikTok token refresh",
    "TikTok draft reminder",
    "Daily summary (stats + charts + ideas)",
    "Topics refresh (dynamic pool)",
}


def _api_get(path: str, token: str) -> dict:
    req = urllib.request.Request(
        f"{GH_API}{path}",
        headers={"Authorization": f"Bearer {token}",
                  "Accept": "application/vnd.github+json"},
    )
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return json.loads(urllib.request.urlopen(req, context=ctx, timeout=30).read())


def _api_post(path: str, token: str, body: dict | None = None) -> int:
    data = json.dumps(body or {}).encode() if body is not None else b""
    req = urllib.request.Request(
        f"{GH_API}{path}",
        data=data, method="POST",
        headers={"Authorization": f"Bearer {token}",
                  "Accept": "application/vnd.github+json",
                  "Content-Type": "application/json"},
    )
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    resp = urllib.request.urlopen(req, context=ctx, timeout=30)
    return resp.status


def retry_recent_failures(minutes_lookback: int = 90) -> dict:
    """Escanea runs fallidos en los últimos N minutos y los relanza."""
    from .notify_batch import add

    token = (os.environ.get("REPO_ADMIN_PAT", "").strip() or
              os.environ.get("GITHUB_TOKEN", "").strip())
    if not token:
        return {"status": "no_token"}

    now = datetime.now(timezone.utc)
    since = now - timedelta(minutes=minutes_lookback)
    since_iso = since.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Listar runs con estado failure creados desde `since`
    try:
        data = _api_get(
            f"/repos/{REPO}/actions/runs?status=failure&created=>{since_iso}&per_page=50",
            token,
        )
    except Exception as e:
        return {"status": "api_error", "error": str(e)[:120]}

    runs = data.get("workflow_runs", [])
    if not runs:
        print("retry: 0 runs failed en los últimos 90 min · nada que hacer")
        return {"status": "ok", "checked": 0, "retried": 0}

    retried, skipped = [], []
    for r in runs:
        name = r.get("name", "?")
        wf_id = r.get("id")
        attempts = r.get("run_attempt", 1)

        # Skip mantenimiento (ya tienen su propia lógica)
        if name in SKIP_WORKFLOWS:
            skipped.append(f"{name} (mantenimiento)")
            continue
        # Skip si ya se re-ejecutó (evita loop)
        if attempts > 1:
            skipped.append(f"{name} (ya reintentado x{attempts})")
            continue

        # Retry: re-ejecuta solo los jobs failed
        try:
            status = _api_post(
                f"/repos/{REPO}/actions/runs/{wf_id}/rerun-failed-jobs", token,
            )
            if status < 300:
                retried.append(name)
                print(f"  🔁 retry {name} ({wf_id})")
            else:
                skipped.append(f"{name} (HTTP {status})")
        except Exception as e:
            skipped.append(f"{name} ({type(e).__name__})")

    # Notif Telegram (solo si hubo reintentos, para no spamear)
    if retried:
        lines = ["🔁 <b>Auto-retry workflows failed</b>"]
        for name in retried[:10]:
            lines.append(f"  • {name}")
        if len(retried) > 10:
            lines.append(f"  … y {len(retried)-10} más")
        lines.append(f"\n<i>Los reintentaré 1 vez más. Si vuelven a fallar, "
                       f"quedan como failure hasta acción manual.</i>")
        add("\n".join(lines))

    print(f"retry: {len(retried)} relanzados, {len(skipped)} saltados")
    return {"status": "ok", "checked": len(runs),
             "retried": retried, "skipped": skipped}
