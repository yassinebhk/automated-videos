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
    r = requests.get(
        "https://pixabay.com/api/audio/",
        params={"key": key, "q": "rain", "per_page": 3}, timeout=_TIMEOUT,
    )
    ct = r.headers.get("content-type", "")
    if "json" not in ct:
        return False, f"content-type {ct[:40]} (posible rate-limit)"
    if r.status_code == 200:
        hits = r.json().get("totalHits", 0)
        return True, f"{hits} hits para query 'rain'"
    return False, f"HTTP {r.status_code}"


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
    name_to_prefix = {name: prefix for prefix, name in YT_CHANNELS}
    sent = 0
    for name, r in yt_results.items():
        if r.get("ok"):
            continue
        prefix = name_to_prefix.get(name, "")
        url = f"{webhook}/api/yt-auth?t={chat}"
        if prefix:
            url += f"&channel={prefix}"
        kb = {"inline_keyboard": [[{"text": f"🔐 Renovar token · {name}", "url": url}]]}
        text = (f"🚨 <b>Token YT caducado: {name}</b>\n"
                f"Toca el botón → elige <b>{name}</b> en Google → se actualiza solo.")
        try:
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          json={"chat_id": chat, "text": text, "parse_mode": "HTML",
                                "reply_markup": kb}, timeout=15)
            sent += 1
        except Exception as e:
            print(f"  reauth button fail {name}: {e}")
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
        "Pixabay":      _safe(_check_pixabay, "Pixabay"),
        "Pollinations": _safe(_check_pollinations, "Pollinations"),
        "Pexels":       _safe(_check_pexels, "Pexels"),
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
