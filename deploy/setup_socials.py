"""Setup helper — muestra qué RRSS están activas + guía para activar las que faltan.

Uso: `python3 deploy/setup_socials.py`

No modifica nada. Solo lee GitHub Secrets vía `gh secret list` y muestra:
- Qué canales están ✅ activos (secrets todas puestas)
- Qué canales están 🔴 dormidos + instrucciones paso-a-paso para activar
- Feed URL del podcast + estado de GH Pages

Ejecuta este script cuando quieras ver el estado o después de añadir un secret.
"""
from __future__ import annotations

import subprocess
import sys
from typing import Optional


def get_secrets() -> set[str]:
    """Lista nombres de secrets del repo actual."""
    try:
        out = subprocess.run(
            ["gh", "secret", "list", "--json", "name"],
            capture_output=True, text=True, check=True,
        ).stdout
        import json
        return {row["name"] for row in json.loads(out)}
    except Exception as e:
        print(f"⚠ No pude listar secrets ({e}). ¿Estás en el repo + gh instalado?")
        sys.exit(1)


CHANNELS = [
    {
        "name": "🎬 YouTube",
        "required": ["YT_REFRESH_TOKEN", "YT_CLIENT_ID", "YT_CLIENT_SECRET"],
        "status_note": "Activo por defecto — reauth cada 7 días vía botón Telegram.",
        "setup_url": None,
    },
    {
        "name": "🎙️ Podcast (Spotify/Apple/iVoox)",
        "required": [],  # no requiere secrets, solo GH Pages activo
        "status_note": (
            "Requiere GitHub Pages activo. Submit URL feed:\n"
            "   https://yassinebhk.github.io/automated-videos/podcasts/feed.xml\n"
            "   Setup: docs/podcasts/README.md"
        ),
        "setup_url": "https://github.com/yassinebhk/automated-videos/settings/pages",
    },
    {
        "name": "🦋 Bluesky",
        "required": ["BLUESKY_HANDLE", "BLUESKY_APP_PASSWORD"],
        "setup_url": "https://bsky.app/settings/app-passwords",
        "setup_steps": [
            "1. Ir a bsky.app/settings/app-passwords",
            "2. Generate app-password → copia",
            "3. gh secret set BLUESKY_HANDLE (tu @handle)",
            "4. gh secret set BLUESKY_APP_PASSWORD",
        ],
    },
    {
        "name": "🐘 Mastodon",
        "required": ["MASTODON_INSTANCE", "MASTODON_ACCESS_TOKEN"],
        "setup_url": "https://mastodon.social/settings/applications",
        "setup_steps": [
            "1. En tu instancia Mastodon → Ajustes → Aplicaciones → Nueva",
            "2. Nombre 'WaitWhy Bot', scopes: read + write",
            "3. gh secret set MASTODON_INSTANCE (ej. https://mastodon.social)",
            "4. gh secret set MASTODON_ACCESS_TOKEN (el token de acceso)",
        ],
    },
    {
        "name": "🐦 X / Twitter",
        "required": ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET"],
        "setup_url": "https://developer.twitter.com/en/portal/dashboard",
        "setup_steps": [
            "1. developer.twitter.com/en/portal/dashboard → Sign up (Free tier)",
            "2. Create App → Setup → App permissions: 'Read and write'",
            "3. Keys and tokens → Copia los 4 valores (regenera Access Token si es solo-read):",
            "   - API Key                  → X_API_KEY",
            "   - API Key Secret           → X_API_SECRET",
            "   - Access Token             → X_ACCESS_TOKEN",
            "   - Access Token Secret      → X_ACCESS_SECRET",
            "4. gh secret set X_API_KEY   (repite los 4)",
            "Free tier: 500 tweets/mes = ~16/día — sobrado.",
        ],
    },
    {
        "name": "📸 Instagram Reels",
        "required": ["IG_ACCESS_TOKEN", "IG_BUSINESS_ACCOUNT_ID"],
        "setup_url": "https://developers.facebook.com/apps",
        "setup_steps": [
            "1. Cuenta IG → Cambiar a 'Cuenta Profesional' (Business o Creator, gratis)",
            "2. Conectar la cuenta IG a una Facebook Page (Meta Business Suite)",
            "3. developers.facebook.com/apps → Create App (tipo: Business)",
            "4. Add Product: Instagram → Instagram Graph API",
            "5. Graph API Explorer: generar token con permisos:",
            "   - instagram_content_publish",
            "   - instagram_basic",
            "   - pages_show_list",
            "6. Intercambiar por long-lived token (60 días, via /oauth/access_token)",
            "7. GET /me/accounts → coge el 'instagram_business_account.id'",
            "8. gh secret set IG_ACCESS_TOKEN (long-lived)",
            "9. gh secret set IG_BUSINESS_ACCOUNT_ID",
        ],
    },
    {
        "name": "🧵 Threads",
        "required": ["THREADS_ACCESS_TOKEN", "THREADS_USER_ID"],
        "setup_url": "https://developers.facebook.com/apps",
        "setup_steps": [
            "1. Mismo app FB que IG (paso 3 de arriba)",
            "2. Add Product: 'Threads'",
            "3. Threads API → generar user access token",
            "4. Permisos: threads_basic + threads_content_publish",
            "5. GET graph.threads.net/v1.0/me → coge el 'id'",
            "6. gh secret set THREADS_ACCESS_TOKEN",
            "7. gh secret set THREADS_USER_ID",
        ],
    },
    {
        "name": "🔴 Reddit",
        "required": ["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USERNAME", "REDDIT_PASSWORD"],
        "setup_url": "https://www.reddit.com/prefs/apps",
        "setup_steps": [
            "1. reddit.com/prefs/apps → 'create app' → type: 'script'",
            "2. Nombre: 'WaitWhy Bot', redirect: http://localhost",
            "3. Copia:",
            "   - client_id (bajo el nombre de la app)",
            "   - secret",
            "4. gh secret set REDDIT_CLIENT_ID",
            "5. gh secret set REDDIT_CLIENT_SECRET",
            "6. gh secret set REDDIT_USERNAME (tu user reddit)",
            "7. gh secret set REDDIT_PASSWORD (tu pass — solo se guarda en GH cifrado)",
        ],
    },
]


def check_channel(channel: dict, secrets: set[str]) -> tuple[bool, list[str]]:
    """Devuelve (ok, missing_secrets)."""
    missing = [s for s in channel["required"] if s not in secrets]
    return (len(missing) == 0, missing)


def print_channel(channel: dict, secrets: set[str]):
    ok, missing = check_channel(channel, secrets)
    mark = "✅" if ok else "🔴"
    print(f"\n{mark} {channel['name']}")
    if ok:
        print(f"   activo — {len(channel['required'])} secrets configuradas")
        if channel.get("status_note"):
            print(f"   {channel['status_note']}")
    else:
        if channel["required"]:
            print(f"   falta {len(missing)}/{len(channel['required'])} secrets: {', '.join(missing)}")
        if channel.get("status_note"):
            print(f"   {channel['status_note']}")
        if channel.get("setup_url"):
            print(f"   URL setup: {channel['setup_url']}")
        if channel.get("setup_steps"):
            print(f"   Pasos:")
            for step in channel["setup_steps"]:
                print(f"      {step}")


def main():
    print("═" * 70)
    print("  WaitWhy — Estado de canales sociales automatizados")
    print("═" * 70)
    secrets = get_secrets()
    ok_count = 0
    for ch in CHANNELS:
        print_channel(ch, secrets)
        ok, _ = check_channel(ch, secrets)
        if ok:
            ok_count += 1
    print()
    print("═" * 70)
    print(f"  RESUMEN: {ok_count}/{len(CHANNELS)} canales activos")
    print("═" * 70)
    print()
    print("Después de añadir cualquier secret nueva, el próximo run del")
    print("workflow (autogen o longgen) la usará automáticamente.")
    print()
    print("Para test manual sin esperar cron:")
    print("  gh workflow run daily-short.yml")


if __name__ == "__main__":
    main()
