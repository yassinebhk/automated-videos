"""Health-check preventivo del ecosistema.

Chequea cada 6h el estado de TODOS los servicios externos y creds:
  - LLMs: Gemini, OpenRouter, Groq
  - Media APIs: Pixabay, Pollinations, Pexels
  - Social: IG, Threads, Bluesky, Mastodon
  - YouTube: los 9 canales (creds válidas + token no expirado)

Notif Telegram con estado ✅/❌ + acción sugerida cuando algo huele mal.

Objetivo: detectar problemas ANTES de que un cron real falle y perdamos
un slot de publicación. Filosofía: cada fallo hoy = video perdido mañana.
"""
from __future__ import annotations

import os
from typing import Any, Callable

# Timeout corto — health-check debe ser rápido. Si algo tarda >10s ya
# lo consideramos degradado.
_TIMEOUT = 10


def _safe(fn: Callable[[], tuple[bool, str]], name: str) -> dict:
    """Ejecuta el check protegido. Devuelve dict con status/detail."""
    try:
        ok, detail = fn()
        return {"ok": ok, "detail": detail[:200] if detail else ""}
    except Exception as e:
        return {"ok": False, "detail": f"{type(e).__name__}: {str(e)[:150]}"}


# ─── LLMs ───

def _check_gemini() -> tuple[bool, str]:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        return False, "no GEMINI_API_KEY"
    import requests
    r = requests.get(
        "https://generativelanguage.googleapis.com/v1beta/models",
        params={"key": key}, timeout=_TIMEOUT,
    )
    if r.status_code == 200:
        n = len(r.json().get("models", []))
        return True, f"{n} modelos disponibles"
    return False, f"HTTP {r.status_code}: {r.text[:80]}"


def _check_openrouter() -> tuple[bool, str]:
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        return False, "no OPENROUTER_API_KEY"
    import requests
    r = requests.get(
        "https://openrouter.ai/api/v1/auth/key",
        headers={"Authorization": f"Bearer {key}"}, timeout=_TIMEOUT,
    )
    if r.status_code == 200:
        return True, "auth OK"
    return False, f"HTTP {r.status_code}"


def _check_groq() -> tuple[bool, str]:
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        return False, "no GROQ_API_KEY"
    import requests
    r = requests.get(
        "https://api.groq.com/openai/v1/models",
        headers={"Authorization": f"Bearer {key}"}, timeout=_TIMEOUT,
    )
    if r.status_code == 200:
        return True, "auth OK"
    return False, f"HTTP {r.status_code}"


# ─── Media APIs ───

def _check_pixabay() -> tuple[bool, str]:
    key = os.environ.get("PIXABAY_API_KEY", "").strip()
    if not key:
        return False, "no PIXABAY_API_KEY"
    import requests
    _UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    # OJO 20/09: Pixabay CERRÓ su API de audio (403). Su uso real ahora es sólo
    # imágenes (fallback de Pexels), así que chequeamos ESE endpoint. La música
    # se sirve por Freesound (ver _check_freesound). Body es text/html con JSON dentro.
    try:
        r = requests.get("https://pixabay.com/api/",
                         params={"key": key, "q": "nature", "per_page": 3, "image_type": "photo"},
                         headers={"User-Agent": _UA}, timeout=_TIMEOUT)
        data = r.json()
    except Exception as e:
        return False, f"error: {str(e)[:50]}"
    if r.status_code == 200 and isinstance(data, dict) and "hits" in data:
        return True, f"imágenes OK ({data.get('totalHits', 0)} hits)"
    return False, f"HTTP {r.status_code}: {str(data)[:50]}"


def _check_freesound() -> tuple[bool, str]:
    key = os.environ.get("FREESOUND_API_KEY", "").strip()
    if not key:
        return False, "no FREESOUND_API_KEY"
    import requests
    try:
        r = requests.get("https://freesound.org/apiv2/search/text/",
                         headers={"Authorization": f"Token {key}"},
                         params={"query": "upbeat", "page_size": 3, "fields": "id"},
                         timeout=_TIMEOUT)
        data = r.json()
        if r.status_code == 200 and "results" in data:
            return True, f"música OK ({data.get('count', 0)} results)"
        return False, f"HTTP {r.status_code}: {str(data)[:50]}"
    except Exception as e:
        return False, f"error: {str(e)[:50]}"


def _check_pollinations() -> tuple[bool, str]:
    import requests
    r = requests.get(
        "https://image.pollinations.ai/prompt/test",
        params={"width": 128, "height": 128, "nologo": "true"},
        timeout=_TIMEOUT,
    )
    ct = r.headers.get("content-type", "")
    if r.status_code == 200 and "image" in ct:
        return True, f"servicio OK ({len(r.content)}b)"
    return False, f"HTTP {r.status_code} ct={ct[:30]}"


def _check_pexels() -> tuple[bool, str]:
    key = os.environ.get("PEXELS_API_KEY", "").strip()
    if not key:
        return False, "no PEXELS_API_KEY (fallback Pollinations aún operativo)"
    import requests
    r = requests.get(
        "https://api.pexels.com/v1/search",
        headers={"Authorization": key},
        params={"query": "test", "per_page": 1}, timeout=_TIMEOUT,
    )
    if r.status_code == 200:
        return True, "auth OK"
    return False, f"HTTP {r.status_code}"


# ─── Social ───

def _check_instagram() -> tuple[bool, str]:
    tok = os.environ.get("IG_TOKEN", "").strip()
    uid = os.environ.get("IG_USER_ID", "").strip()
    if not tok or not uid:
        return False, "no IG_TOKEN / IG_USER_ID"
    import requests
    r = requests.get(
        f"https://graph.instagram.com/v21.0/{uid}",
        params={"fields": "username", "access_token": tok},
        timeout=_TIMEOUT,
    )
    if r.status_code == 200:
        return True, f"@{r.json().get('username','?')}"
    return False, f"HTTP {r.status_code} — token quizá caducado (IG dura 60d)"


def _check_threads() -> tuple[bool, str]:
    tok = os.environ.get("THREADS_TOKEN", "").strip() or \
          os.environ.get("THREADS_ACCESS_TOKEN", "").strip()
    if not tok:
        return False, "no THREADS_TOKEN"
    import requests
    r = requests.get(
        "https://graph.threads.net/v1.0/me",
        params={"fields": "username", "access_token": tok},
        timeout=_TIMEOUT,
    )
    if r.status_code == 200:
        return True, f"@{r.json().get('username','?')}"
    return False, f"HTTP {r.status_code} — token quizá caducado"


def _check_bluesky() -> tuple[bool, str]:
    handle = os.environ.get("BLUESKY_HANDLE", "").strip()
    pwd = os.environ.get("BLUESKY_APP_PASSWORD", "").strip()
    if not handle or not pwd:
        return False, "no BLUESKY_HANDLE/APP_PASSWORD"
    try:
        from atproto import Client
        c = Client()
        c.login(handle, pwd)
        return True, f"@{handle}"
    except Exception as e:
        return False, f"login fail: {str(e)[:80]}"


def _check_mastodon() -> tuple[bool, str]:
    tok = os.environ.get("MASTODON_ACCESS_TOKEN", "").strip()
    inst = os.environ.get("MASTODON_INSTANCE", "https://mastodon.social").rstrip("/")
    if not tok:
        return False, "no MASTODON_ACCESS_TOKEN"
    import requests
    r = requests.get(
        f"{inst}/api/v1/accounts/verify_credentials",
        headers={"Authorization": f"Bearer {tok}"}, timeout=_TIMEOUT,
    )
    if r.status_code == 200:
        return True, f"@{r.json().get('username','?')}@{inst.split('//')[-1]}"
    return False, f"HTTP {r.status_code}"


# ─── YouTube (9 canales) ───

YT_CHANNELS = [
    ("", "WaitWhy"),
    ("YT_TAX", "TaxHack ES"),
    ("YT_LEGAL", "TusDerechos ES"),
    ("YT_AYUDAS", "AyudaGob"),
    ("YT_MOTOR", "Motor60s"),
    ("YT_POV", "TiempoAtrás ES"),
    ("YT_RANKING", "TopRanking ES"),
    ("YT_AMBIENT", "MenteEnCalma"),
    ("YT_IA", "IA Autónomos ES"),
]


def _check_youtube_channel(prefix: str, name: str) -> tuple[bool, str]:
    prev = os.environ.get("YT_CHANNEL_PREFIX", "")
    if prefix:
        os.environ["YT_CHANNEL_PREFIX"] = prefix
    else:
        os.environ.pop("YT_CHANNEL_PREFIX", None)
    try:
        from .upload_youtube import _get_credentials
        import googleapiclient.discovery
        creds = _get_credentials()
        yt = googleapiclient.discovery.build("youtube", "v3", credentials=creds)
        r = yt.channels().list(part="id", mine=True).execute()
        items = r.get("items", [])
        if items:
            return True, f"channel_id={items[0]['id'][:12]}"
        return False, "channels.list vacío"
    finally:
        if prev:
            os.environ["YT_CHANNEL_PREFIX"] = prev
        else:
            os.environ.pop("YT_CHANNEL_PREFIX", None)


# ─── Runner principal ───

def _send_reauth_buttons(yt_results: dict) -> int:
    """Por CADA canal YT con token caído, manda a Telegram un BOTÓN de reauth
    específico de ese canal (abre el OAuth del canal y actualiza SU secret).

    Requiere WEBHOOK_URL (flujo web OAuth por-canal) + TELEGRAM_BOT_TOKEN/CHAT_ID.
    """
    import requests
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    webhook = os.environ.get("WEBHOOK_URL", "").rstrip("/")
    if not (token and chat and webhook):
        print("  reauth: falta WEBHOOK_URL/TELEGRAM_* — no puedo mandar botones")
        return 0
    def _post(text, kb):
        try:
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          json={"chat_id": chat, "text": text, "parse_mode": "HTML",
                                "reply_markup": kb}, timeout=15)
            return True
        except Exception as e:
            print(f"  reauth button post fail: {e}")
            return False

    name_to_prefix = {name: prefix for prefix, name in YT_CHANNELS}
    down = [(name, name_to_prefix.get(name, "")) for name, r in yt_results.items() if not r.get("ok")]
    down_prefixed = [(n, p) for (n, p) in down if p]  # el principal (prefix "") va aparte
    sent = 0

    # 🔐 Botón "RENOVAR TODOS" (cadena) — un clic renueva todos en secuencia
    if len(down_prefixed) >= 2:
        allp = ",".join(p for _, p in down_prefixed)
        url = f"{webhook}/api/yt-auth?t={chat}&channels={allp}"
        lst = "\n".join(f"• {n}" for n, _ in down_prefixed)
        kb = {"inline_keyboard": [[{"text": f"🔐 RENOVAR TODOS ({len(down_prefixed)})", "url": url}]]}
        text = (f"🚨 <b>{len(down_prefixed)} tokens YT caducados</b>\n"
                f"Toca para renovarlos TODOS en cadena (Google te pedirá elegir cada canal, "
                f"uno tras otro):\n{lst}")
        if _post(text, kb):
            sent += 1

    # Botones individuales (por si quieres renovar solo uno)
    for name, prefix in down:
        url = f"{webhook}/api/yt-auth?t={chat}"
        if prefix:
            url += f"&channel={prefix}"
        kb = {"inline_keyboard": [[{"text": f"🔐 Renovar · {name}", "url": url}]]}
        text = (f"🔸 <b>{name}</b> — o renueva solo este (elige <b>{name}</b> en Google).")
        if _post(text, kb):
            sent += 1
    return sent


def check_all() -> dict[str, Any]:
    """Ejecuta todos los checks y notifica Telegram con resumen."""
    from .notify_batch import add

    print("🩺 healthcheck: iniciando…")

    llms = {
        "Gemini":       _safe(_check_gemini, "Gemini"),
        "OpenRouter":   _safe(_check_openrouter, "OpenRouter"),
        "Groq":         _safe(_check_groq, "Groq"),
    }
    media = {
        "Pixabay(img)": _safe(_check_pixabay, "Pixabay"),
        "Pollinations": _safe(_check_pollinations, "Pollinations"),
        "Pexels":       _safe(_check_pexels, "Pexels"),
        "Freesound(música)": _safe(_check_freesound, "Freesound"),
    }
    social = {
        "Instagram":    _safe(_check_instagram, "Instagram"),
        "Threads":      _safe(_check_threads, "Threads"),
        "Bluesky":      _safe(_check_bluesky, "Bluesky"),
        "Mastodon":     _safe(_check_mastodon, "Mastodon"),
    }
    yt = {}
    for prefix, name in YT_CHANNELS:
        yt[name] = _safe(lambda p=prefix, n=name: _check_youtube_channel(p, n), name)

    def _fmt_group(title: str, items: dict) -> list[str]:
        lines = [f"<b>{title}</b>"]
        for name, r in items.items():
            icon = "✅" if r["ok"] else "❌"
            detail = r["detail"] if r["detail"] else ""
            lines.append(f"  {icon} {name}: {detail[:80]}")
        return lines

    lines = ["🩺 <b>Health-check ecosistema</b>", ""]
    lines += _fmt_group("LLMs", llms) + [""]
    lines += _fmt_group("Media", media) + [""]
    lines += _fmt_group("Social", social) + [""]
    lines += _fmt_group("YouTube canales", yt) + [""]

    # Alertas urgentes agrupadas — para que el user vea de un vistazo
    # qué necesita acción MANUAL YA
    down = []
    for group in (llms, media, social, yt):
        for name, r in group.items():
            if not r["ok"]:
                down.append(name)
    if down:
        lines.append(f"⚠️ <b>Servicios caídos ({len(down)})</b>: {', '.join(down)}")
    else:
        lines.append("✨ <b>Todo verde</b> — ecosistema al 100%")

    msg = "\n".join(lines)
    add(msg)
    print(msg)

    # 🔐 Botón de reauth POR CANAL para cada YT con token caducado → llega solo
    # a Telegram, uno por canal (petición user 19/09).
    yt_down = [n for n, r in yt.items() if not r["ok"]]
    if yt_down:
        n_btn = _send_reauth_buttons(yt)
        print(f"  reauth: {n_btn} botones enviados para {yt_down}")

    return {
        "llms": llms, "media": media, "social": social, "youtube": yt,
        "down_count": len(down), "down_services": down,
    }
