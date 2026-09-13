#!/usr/bin/env python3
"""Genera un REFRESH_TOKEN de YouTube para un canal específico.

Uso:
    # Con el client_secret.json por defecto (secrets/youtube_client_secret.json)
    python3 scripts/get_channel_refresh_token.py

    # Con un JSON específico (recomendado para canales nuevos)
    python3 scripts/get_channel_refresh_token.py /path/to/client_secret.json

Abre el navegador para que autorices con tu cuenta Google. En el
selector de cuenta Google, elige el BRAND ACCOUNT del canal que
quieres autorizar (ej. 'IA Autonomos ES'), no la cuenta personal.

Al terminar imprime el REFRESH_TOKEN + CLIENT_ID + CLIENT_SECRET
para que los añadas como GH Secrets:
    YT_<CHANNEL>_REFRESH_TOKEN
    YT_<CHANNEL>_CLIENT_ID
    YT_<CHANNEL>_CLIENT_SECRET
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_CLIENT_SECRET = REPO / "secrets" / "youtube_client_secret.json"

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


def main() -> None:
    # Permite pasar un JSON custom como primer argumento
    if len(sys.argv) > 1:
        client_secret_path = Path(sys.argv[1]).expanduser().resolve()
    else:
        client_secret_path = DEFAULT_CLIENT_SECRET

    if not client_secret_path.exists():
        print(f"❌ Falta {client_secret_path}")
        print()
        print("SOLUCIÓN:")
        print("  1. Ve a https://console.cloud.google.com/apis/credentials")
        print("  2. Selecciona tu PROYECTO actual (ej. fintack-508312)")
        print("  3. Descarga el JSON del OAuth Client existente (icono ⬇)")
        print("     Si no existe, créalo: '+ Create Credentials' →")
        print("     'OAuth Client ID' → Type: Desktop app → Create")
        print(f"  4. python3 scripts/get_channel_refresh_token.py /ruta/al/descargado.json")
        sys.exit(1)

    with open(client_secret_path) as f:
        cs = json.load(f)
    inst = cs.get("installed") or cs.get("web") or {}
    cid = inst.get("client_id", "")
    csec = inst.get("client_secret", "")
    project = inst.get("project_id", "?")

    if not cid or not csec:
        print(f"❌ JSON inválido en {client_secret_path}: falta client_id o client_secret")
        sys.exit(1)

    print("=" * 62)
    print("OAuth flow YouTube — canal específico")
    print("=" * 62)
    print(f"  📁 client_secret: {client_secret_path.name}")
    print(f"  📦 project_id:    {project}")
    print(f"  🆔 client_id:     …{cid[-40:]}")
    print()
    print("⚠️  IMPORTANTE: cuando se abra el navegador y te pida")
    print("    seleccionar cuenta Google, elige la CUENTA DE MARCA")
    print("    (brand account) del canal que quieres autorizar,")
    print("    no la cuenta personal principal.")
    print()
    print("    Google te preguntará DOS veces:")
    print("    1) primero tu cuenta Google normal")
    print("    2) luego el BRAND ACCOUNT (aparece el canal que creaste)")
    print()
    input("Pulsa Enter para abrir el navegador…")

    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(
        str(client_secret_path), SCOPES,
    )
    creds = flow.run_local_server(port=0, prompt="consent",
                                     access_type="offline")

    print()
    print("=" * 62)
    print("✅ TOKEN OBTENIDO — copia estos 3 valores a GH Secrets:")
    print("=" * 62)
    print()
    print(f"CLIENT_ID     = {cid}")
    print()
    print(f"CLIENT_SECRET = {csec}")
    print()
    print(f"REFRESH_TOKEN = {creds.refresh_token}")
    print()
    print("=" * 62)
    print("👉 URL para añadir/actualizar secrets:")
    print("   https://github.com/yassinebhk/automated-videos/settings/secrets/actions")
    print()
    print("   Para el canal IA_Autonomos_ES son:")
    print("     - YT_IA_CLIENT_ID")
    print("     - YT_IA_CLIENT_SECRET")
    print("     - YT_IA_REFRESH_TOKEN")
    print()


if __name__ == "__main__":
    main()
