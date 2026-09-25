"""Playlists automáticas por case_key.

Palanca: YT algoritmo boostea binge-watching. Si viewer termina video 1 →
sugerido interno lleva a video 2 de la misma playlist → 3× retention.
Fuente evidencia funnel 28d: descubrimiento interno YT es donde vive el
tráfico real (Home/Sugeridos), no RRSS.

Flow:
- Al subir video, `sync_video_to_playlist` recibe video_id + topic.
- match_case_key(topic) → si hay case_key:
  - Cuenta cuántos videos hay en output/uploaded/ del mismo case_key.
  - Si >=3 y la playlist YT aún no existe → la crea.
  - Añade el video a la playlist (idempotente: skip si ya está).

Requiere: token YT con scope `youtube.force-ssl` (ya activo).
Cron catchup: 1×/semana barre uploaded/ y sincroniza retroactivo.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import requests

from .config import ROOT, SECRETS_DIR, UPLOADED_DIR

LEDGER = ROOT / "output" / "playlists_manager_ledger.json"
MIN_VIDEOS_TO_CREATE = 3


def _load_ledger() -> dict:
    if not LEDGER.exists():
        return {"cases": {}}
    try:
        d = json.loads(LEDGER.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) and "cases" in d else {"cases": {}}
    except Exception:
        return {"cases": {}}


def _save_ledger(data: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _access_token() -> Optional[str]:
    """Access token del CANAL ACTUAL (respeta YT_CHANNEL_PREFIX).
    Fallback a token file (WaitWhy principal en dev)."""
    prefix = (os.environ.get("YT_CHANNEL_PREFIX") or "").strip()
    if prefix:
        rt = os.environ.get(f"{prefix}_REFRESH_TOKEN")
        cid = os.environ.get(f"{prefix}_CLIENT_ID") or os.environ.get("YT_CLIENT_ID")
        csec = os.environ.get(f"{prefix}_CLIENT_SECRET") or os.environ.get("YT_CLIENT_SECRET")
        if rt and cid and csec:
            r = requests.post("https://oauth2.googleapis.com/token", data={
                "client_id": cid, "client_secret": csec,
                "refresh_token": rt, "grant_type": "refresh_token",
            }, timeout=15).json()
            return r.get("access_token")
    rt = os.environ.get("YT_REFRESH_TOKEN")
    cid = os.environ.get("YT_CLIENT_ID"); csec = os.environ.get("YT_CLIENT_SECRET")
    if rt and cid and csec:
        r = requests.post("https://oauth2.googleapis.com/token", data={
            "client_id": cid, "client_secret": csec,
            "refresh_token": rt, "grant_type": "refresh_token",
        }, timeout=15).json()
        return r.get("access_token")
    tok_path = SECRETS_DIR / "youtube_token.json"
    if tok_path.exists():
        tok = json.loads(tok_path.read_text())
        r = requests.post("https://oauth2.googleapis.com/token", data={
            "client_id": tok["client_id"], "client_secret": tok["client_secret"],
            "refresh_token": tok["refresh_token"], "grant_type": "refresh_token",
        }, timeout=15).json()
        return r.get("access_token")
    return None


def _pretty_case_title(case_key: str) -> str:
    """kio → 'Caso KIO — Serie completa' · barcenas → 'Caso Bárcenas — Serie completa'."""
    special = {
        "kio": "KIO",
        "gurtel": "Gürtel",
        "barcenas": "Bárcenas",
        "malaya": "Malaya",
        "villarejo": "Villarejo",
        "roldan": "Roldán",
        "banesto": "Banesto (Mario Conde)",
        "erial": "Erial (Zaplana)",
        "koldo": "Koldo",
        "rumasa": "RUMASA",
        "grand_tibidabo": "Grand Tibidabo",
    }
    name = special.get(case_key, case_key.replace("_", " ").title())
    return f"Caso {name} — Serie completa"


def _count_case_videos_local(case_key: str) -> int:
    """Cuenta cuántos videos del case existen en output/uploaded/ (por match_case_key)."""
    from . import case_ledger
    if not UPLOADED_DIR.exists():
        return 0
    count = 0
    for d in UPLOADED_DIR.iterdir():
        if not d.is_dir():
            continue
        yt = d / "youtube.json"
        if not yt.exists():
            continue
        try:
            data = json.loads(yt.read_text(encoding="utf-8"))
        except Exception:
            continue
        # match por slug (nombre carpeta) o title dentro del json
        candidates = [d.name] + [v for k, v in data.items() if isinstance(v, str) and k not in ("_ids", "_title_variants")]
        for c in candidates:
            if case_ledger.match_case_key(c) == case_key:
                count += 1
                break
    return count


def _create_playlist(tok: str, title: str, description: str = "") -> Optional[str]:
    H = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}
    body = {
        "snippet": {"title": title[:150], "description": description[:5000]},
        "status": {"privacyStatus": "public"},
    }
    r = requests.post("https://www.googleapis.com/youtube/v3/playlists",
                      params={"part": "snippet,status"},
                      headers=H, json=body, timeout=20)
    if r.status_code == 200:
        return r.json().get("id")
    print(f"  playlists: create fail {r.status_code} — {r.text[:180]}")
    return None


def _add_to_playlist(tok: str, playlist_id: str, video_id: str) -> bool:
    H = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}
    body = {
        "snippet": {
            "playlistId": playlist_id,
            "resourceId": {"kind": "youtube#video", "videoId": video_id},
        }
    }
    r = requests.post("https://www.googleapis.com/youtube/v3/playlistItems",
                      params={"part": "snippet"}, headers=H, json=body, timeout=20)
    if r.status_code == 200:
        return True
    # 409 = ya está en la playlist → OK
    if r.status_code == 409 or "video already" in r.text.lower():
        return True
    print(f"  playlists: add {video_id}→{playlist_id} fail {r.status_code} — {r.text[:180]}")
    return False


def sync_video_to_playlist(video_id: str, topic_or_title: str) -> dict:
    """Añade video a la playlist del case (crea si toca). Devuelve dict resultado.
    Idempotente: si el video ya está registrado, no hace nada."""
    from . import case_ledger
    case_key = case_ledger.match_case_key(topic_or_title or "")
    if not case_key:
        return {"skipped": "no case_key"}

    ledger = _load_ledger()
    entry = ledger["cases"].setdefault(case_key, {"playlist_id": None, "video_ids": []})
    if video_id in entry["video_ids"]:
        return {"skipped": "already synced", "case_key": case_key}

    tok = _access_token()
    if not tok:
        return {"error": "no YT token"}

    # ¿Crear playlist? Solo si hay >=3 videos locales del caso y aún no existe.
    if not entry["playlist_id"]:
        local_count = _count_case_videos_local(case_key)
        if local_count < MIN_VIDEOS_TO_CREATE:
            entry["video_ids"].append(video_id)
            _save_ledger(ledger)
            return {"deferred": f"only {local_count} videos, need {MIN_VIDEOS_TO_CREATE}",
                    "case_key": case_key}
        pl_title = _pretty_case_title(case_key)
        pl_desc = (f"Toda la serie sobre este caso español real, con fuentes citables. "
                   f"Sentencias, cifras y consecuencias — un video por parte.")
        pl_id = _create_playlist(tok, pl_title, pl_desc)
        if not pl_id:
            return {"error": "playlist create fail"}
        entry["playlist_id"] = pl_id
        print(f"  playlists: ✅ creada «{pl_title}» → {pl_id}")

    # Añadir video (y los pendientes previos del ledger)
    added = 0
    for vid in list(entry["video_ids"]) + [video_id]:
        if _add_to_playlist(tok, entry["playlist_id"], vid):
            if vid not in entry["video_ids"]:
                entry["video_ids"].append(vid)
                added += 1
    _save_ledger(ledger)
    return {"case_key": case_key, "playlist_id": entry["playlist_id"],
            "added": added, "total_in_playlist": len(entry["video_ids"])}


def catchup_all_cases() -> dict:
    """Barre output/uploaded/ y sincroniza retroactivamente cada video al
    playlist de su case_key. Cron 1×/semana."""
    from . import case_ledger
    if not UPLOADED_DIR.exists():
        return {"checked": 0, "synced": 0}
    synced = errors = 0
    for d in sorted(UPLOADED_DIR.iterdir()):
        if not d.is_dir():
            continue
        yt = d / "youtube.json"
        if not yt.exists():
            continue
        try:
            data = json.loads(yt.read_text(encoding="utf-8"))
        except Exception:
            continue
        ids = data.get("_ids") or {}
        video_id = ids.get("es") or ids.get("en")
        if not video_id:
            continue
        # topic candidate: slug carpeta
        topic = d.name.replace("-", " ")
        res = sync_video_to_playlist(video_id, topic)
        if "case_key" in res and "error" not in res:
            synced += 1
        elif "error" in res:
            errors += 1
    return {"synced": synced, "errors": errors}
