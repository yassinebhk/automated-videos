"""Auto-gestión de playlists segmentadas por categoría de caso.

Estrategia (auditoría 08-07): un solo "Estafas Españolas" en flat no da
binge-watching. YouTube recomienda videos de la MISMA playlist cuando el user
termina el actual → 3× watch time en la sesión. Con 3 sub-playlists (Bancarios,
Políticos, Empresariales), cada tribu (finanzas / política / consumidor)
encuentra su racha inmediata.

Este módulo:
1. Mantiene un JSON persistente con {categoría: playlist_id} en secrets/.
2. Al primer uso, si una playlist no existe → la crea vía YT API y persiste
   el ID. Idempotente entre runs.
3. Clasifica un topic (string) → categoría en base a keywords conocidos.
4. Añade un video (id) a la playlist correcta.

No depende de nada manual: la primera vez que corre en Actions, crea las 3
playlists en el canal automáticamente.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import requests

from .config import SECRETS_DIR


CATEGORIES = {
    "bancarios": {
        "title": "Estafas Bancarias Españolas",
        "description": (
            "Casos reales de fraudes bancarios en España — Bankia, Fórum Filatélico, "
            "Preferentes, Banco Popular, RUMASA. Todo con sentencia judicial firme."
        ),
        "keywords": [
            "bankia", "popular", "banco popular", "preferentes", "fórum", "forum",
            "filatélico", "filatelico", "afinsa", "nummers", "rumasa", "ruiz-mateos",
            "ruiz mateos", "banesto", "mario conde", "gescartera",
        ],
    },
    "politicos": {
        "title": "Corrupción Política en España",
        "description": (
            "Los grandes escándalos políticos con sentencia firme — Gürtel, Bárcenas, "
            "ERE Andalucía, Púnica, Villarejo. Cómo la clase política saqueó España."
        ),
        "keywords": [
            "bárcenas", "barcenas", "gürtel", "gurtel", "correa", "púnica", "punica",
            "ere andalucía", "ere andalucia", "villarejo", "filesa",
            "urdangarin", "nóos", "noos", "mariano rubio", "marta domínguez",
        ],
    },
    "empresariales": {
        "title": "Fraudes Empresariales Españoles",
        "description": (
            "Las grandes estafas del mundo empresarial español — Aceite de Colza, iDental, "
            "Pescanova, Arbistar, MATESA. Víctimas reales, fortunas robadas."
        ),
        "keywords": [
            "colza", "aceite de colza", "idental", "i-dental", "arbistar",
            "kuailian", "pescanova", "matesa", "toni kamo", "airtel", "terra networks",
            "malaya", "marbella", "juan antonio roca", "palma arena", "ibercorp",
        ],
    },
}


_PLAYLIST_MAP_FILE = SECRETS_DIR / "playlists_map.json"


def _load_map() -> dict[str, str]:
    if _PLAYLIST_MAP_FILE.exists():
        try:
            return json.loads(_PLAYLIST_MAP_FILE.read_text())
        except Exception:
            return {}
    return {}


def _save_map(m: dict[str, str]) -> None:
    _PLAYLIST_MAP_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PLAYLIST_MAP_FILE.write_text(json.dumps(m, ensure_ascii=False, indent=2))


def _get_access_token() -> Optional[str]:
    tok_path = SECRETS_DIR / "youtube_token.json"
    if not tok_path.exists():
        return None
    tok = json.loads(tok_path.read_text())
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": tok["client_id"], "client_secret": tok["client_secret"],
        "refresh_token": tok["refresh_token"], "grant_type": "refresh_token",
    }, timeout=15).json()
    return r.get("access_token")


def classify_topic(topic: str) -> str:
    """Devuelve 'bancarios' | 'politicos' | 'empresariales' según el topic.
    Fallback: 'politicos' (por defecto el nicho más amplio en el canal).
    """
    tl = (topic or "").lower()
    for cat, meta in CATEGORIES.items():
        if any(k in tl for k in meta["keywords"]):
            return cat
    return "politicos"


def _create_playlist(access_token: str, title: str, description: str) -> Optional[str]:
    """Crea una playlist en el canal. Devuelve el playlist_id o None si falla."""
    H = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    body = {
        "snippet": {"title": title, "description": description[:5000],
                    "defaultLanguage": "es"},
        "status": {"privacyStatus": "public"},
    }
    r = requests.post("https://www.googleapis.com/youtube/v3/playlists",
                      params={"part": "snippet,status"},
                      headers=H, json=body, timeout=20)
    if r.status_code == 200:
        return r.json()["id"]
    print(f"  playlists: create fail {r.status_code} — {r.text[:200]}")
    return None


def ensure_playlists() -> dict[str, str]:
    """Devuelve {categoria: playlist_id}. Crea las que falten. Idempotente."""
    m = _load_map()
    missing = [c for c in CATEGORIES if c not in m]
    if not missing:
        return m
    tok = _get_access_token()
    if not tok:
        print("  playlists: sin token YT, salto creación")
        return m
    for cat in missing:
        meta = CATEGORIES[cat]
        pid = _create_playlist(tok, meta["title"], meta["description"])
        if pid:
            m[cat] = pid
            print(f"  playlists: ✅ creada '{meta['title']}' → {pid}")
    _save_map(m)
    return m


def add_video_to_category(video_id: str, topic: str) -> Optional[str]:
    """Añade un video a la playlist correspondiente según topic.
    Devuelve categoría usada o None si falla."""
    cat = classify_topic(topic)
    m = ensure_playlists()
    playlist_id = m.get(cat)
    if not playlist_id:
        print(f"  playlists: sin playlist_id para categoría '{cat}'")
        return None
    tok = _get_access_token()
    if not tok:
        return None
    H = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}
    body = {"snippet": {"playlistId": playlist_id,
                        "resourceId": {"kind": "youtube#video", "videoId": video_id}}}
    r = requests.post("https://www.googleapis.com/youtube/v3/playlistItems",
                      params={"part": "snippet"}, headers=H, json=body, timeout=15)
    if r.status_code == 200:
        cat_title = CATEGORIES[cat]["title"]
        print(f"  playlists: ✅ '{video_id}' → «{cat_title}»")
        return cat
    print(f"  playlists: add fail {r.status_code} — {r.text[:200]}")
    return None
