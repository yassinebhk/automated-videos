#!/usr/bin/env python3
"""Genera un REFRESH_TOKEN de YouTube para un canal específico.

Uso:
    python3 scripts/get_channel_refresh_token.py

Abre el navegador para que autorices con tu cuenta Google. En el
selector de cuenta Google, elige el BRAND ACCOUNT del canal que
quieres autorizar (ej. 'IA Autonomos ES'), no la cuenta personal.

Al terminar imprime el REFRESH_TOKEN + CLIENT_ID + CLIENT_SECRET
para que los añadas como GH Secrets:
    YT_IA_REFRESH_TOKEN
    YT_IA_CLIENT_ID
    YT_IA_CLIENT_SECRET
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CLIENT_SECRET = REPO / "secrets" / "youtube_client_secret.json"

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


def main() -> None:
    from google_auth_oauthlib.flow import InstalledAppFlow

    if not CLIENT_SECRET.exists():
        print(f"❌ Falta {CLIENT_SECRET}")
        sys.exit(1)

    with open(CLIENT_SECRET) as f:
        cs = json.load(f)
    inst = cs.get("installed") or cs.get("web") or {}
    cid = inst.get("client_id", "")
    csec = inst.get("client_secret", "")

    print("=" * 60)
    print("OAuth flow YouTube — canal específico")
    print("=" * 60)
    print()
    print("⚠️  IMPORTANTE: cuando se abra el navegador y te pida")
    print("    seleccionar cuenta Google, elige el BRAND ACCOUNT")
    print("    del canal (no la cuenta personal principal).")
    print()
    print("    'IA Autonomos ES' debe aparecer en la lista si lo")
    print("    creaste bien como brand account (cuenta de marca).")
    print()
    input("Pulsa Enter para abrir el navegador…")

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent",
                                     access_type="offline")

    print()
    print("=" * 60)
    print("✅ TOKEN OBTENIDO — copia estos 3 valores a GH Secrets:")
    print("=" * 60)
    print()
    print(f"YT_IA_CLIENT_ID = {cid}")
    print()
    print(f"YT_IA_CLIENT_SECRET = {csec}")
    print()
    print(f"YT_IA_REFRESH_TOKEN = {creds.refresh_token}")
    print()
    print("=" * 60)
    print("👉 URL para añadir secrets:")
    print("   https://github.com/yassinebhk/automated-videos/settings/secrets/actions/new")
    print()


if __name__ == "__main__":
    main()
