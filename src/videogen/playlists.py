"""Auto-playlists YT: agrupa uploads del canal por sub-tema y crea/actualiza
playlists YT via API. Objetivo: +40% session watch time (palanca #1 algoritmo
YT 2026 tras el desacople Shorts/long-form de late 2025).

Uso:
    videogen playlists-refresh         # todos los canales
    videogen playlists-refresh --channel YT_TAX

Cron semanal: .github/workflows/playlists-weekly.yml (domingo 06:00 UTC).

Persistencia: `output/playlists_ledger.json` mapea
    {"<yt_prefix>": {"<playlist_title>": "<playlist_id>"}}
para idempotencia (evita crear la misma playlist 2 veces).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import googleapiclient.discovery

from .config import ROOT
from .upload_youtube import _get_credentials

PLAYLIST_LEDGER = ROOT / "output" / "playlists_ledger.json"


# Sub-temas por canal. Cada playlist agrupa videos cuyos títulos/tags matchen
# CUALQUIER keyword del listado (lowercase, substring match).
# Un video puede estar en múltiples playlists — no pasa nada.
CHANNEL_PLAYLISTS: dict[str, dict[str, list[str]]] = {
    "YT_TAX": {
        "Autónomos 2026 — Deducciones e IRPF": [
            "autónomo", "autonomo", "irpf", "deducci", "iva", "cuota"],
        "Obligaciones fiscales (modelos)": [
            "modelo 130", "modelo 303", "modelo 100", "modelo 349", "modelo 111",
            "trimestral", "declaración"],
        "Trucos y ahorros fiscales": [
            "truco", "ahorro", "hack", "ayuda", "planificación", "optimizar"],
        "Novedades Hacienda 2026": [
            "2026", "nueva", "novedad", "reforma", "cambio"],
    },
    "YT_LEGAL": {
        "Derechos del trabajador ES": [
            "trabajador", "empleado", "jornada", "vacaciones", "salario",
            "despido", "indemnización", "baja"],
        "Contratos y nóminas": [
            "contrato", "nómina", "nomina", "temporal", "indefinido"],
        "Autónomos y freelance": [
            "autónomo", "autonomo", "freelance"],
        "Protección al consumidor": [
            "consumidor", "reclamación", "reclamacion", "garantía", "devolución"],
    },
    "YT_AYUDAS": {
        "Ayudas familias ES 2026": [
            "familia", "hijo", "menor", "cheque", "conciliación"],
        "Ayudas vivienda y alquiler": [
            "vivienda", "alquiler", "hipoteca", "bono alquiler"],
        "Ayudas autónomos y empleo": [
            "autónomo", "autonomo", "empleo", "paro", "formación"],
        "Subvenciones y bonos 2026": [
            "subvención", "subvencion", "bono", "kit digital"],
    },
    "YT_MOTOR": {
        "Comprar coche de segunda mano": [
            "segunda mano", "usado", "km0", "km 0"],
        "Precios y valoración coches": [
            "precio", "valor", "valoración", "cuánto vale"],
        "Cochazos por poco dinero": [
            "por poco", "barato", "bajo presupuesto", "€", "menos de"],
        "Trucos motor y consejos compra": [
            "truco", "consejo", "evita", "no compres", "revisar"],
    },
    "YT_POV": {
        "Grandes hitos históricos": [
            "descubrimiento", "guerra", "batalla", "revolución"],
        "Personajes históricos": [
            "napoleón", "julio césar", "franco", "isabel", "colón",
            "quijote"],
        "Historia de España": [
            "españa", "español", "hispano", "conquistador"],
        "Historia universal": [
            "mundo", "universal", "civilización", "imperio"],
    },
    "YT_RANKING": {
        "Rankings riqueza y millonarios": [
            "millonario", "billonario", "riqueza", "ricos", "forbes",
            "fortunas"],
        "Rankings deportivos": [
            "goleador", "champions", "mundial", "olimpiada", "récord",
            "campeón"],
        "Rankings tecnología y empresas": [
            "empresas", "startup", "unicorn", "tech", "silicon",
            "capitalización"],
        "Rankings países y ciudades": [
            "país", "pais", "ciudad", "población", "pib", "índice"],
    },
    "YT_AMBIENT": {
        "Sonidos naturaleza para relajarse": [
            "lluvia", "olas", "río", "rio", "bosque", "naturaleza"],
        "Ambientes para estudiar y concentrarse": [
            "estudio", "estudiar", "concentración", "focus", "trabajo"],
        "Sonidos para dormir": [
            "dormir", "sueño", "insomnio", "noche"],
        "Ruido blanco y meditación": [
            "ruido blanco", "meditación", "meditacion", "mindfulness"],
    },
    # WaitWhy (default sin prefijo) — true crime
    "": {
        "Estafas famosas de España": [
            "estafa", "fraude", "engaño", "pirámide"],
        "Casos de asesinato reales ES": [
            "asesinato", "crimen", "homicidio", "muerte"],
        "Casos sin resolver": [
            "sin resolver", "cold case", "misterio", "desaparición"],
        "Grandes robos españoles": [
            "robo", "atraco", "hurto"],
    },
}


def _load_ledger() -> dict[str, dict[str, str]]:
    if not PLAYLIST_LEDGER.exists():
        return {}
    try:
        return json.loads(PLAYLIST_LEDGER.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_ledger(led: dict[str, dict[str, str]]) -> None:
    PLAYLIST_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    PLAYLIST_LEDGER.write_text(
        json.dumps(led, indent=2, ensure_ascii=False), encoding="utf-8",
    )


def _list_uploads(youtube: Any, max_results: int = 50) -> list[dict]:
    """Devuelve últimos N uploads del canal autenticado, con id/title."""
    ch = youtube.channels().list(part="contentDetails", mine=True).execute()
    items = ch.get("items", [])
    if not items:
        return []
    uploads_pl = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

    out: list[dict] = []
    next_page = None
    while len(out) < max_results:
        req = youtube.playlistItems().list(
            part="snippet,contentDetails", playlistId=uploads_pl,
            maxResults=min(50, max_results - len(out)), pageToken=next_page,
        )
        resp = req.execute()
        for it in resp.get("items", []):
            out.append({
                "id": it["contentDetails"]["videoId"],
                "title": it["snippet"]["title"],
            })
        next_page = resp.get("nextPageToken")
        if not next_page:
            break
    return out


def _ensure_playlist(youtube: Any, ledger_ch: dict[str, str],
                       title: str, description: str) -> str | None:
    """Devuelve el id de la playlist. Crea si no existe."""
    pid = ledger_ch.get(title)
    if pid:
        # Verifica que aún existe (podría estar borrada)
        try:
            resp = youtube.playlists().list(part="id", id=pid).execute()
            if resp.get("items"):
                return pid
        except Exception:
            pass
    # Crea nueva
    try:
        resp = youtube.playlists().insert(
            part="snippet,status",
            body={
                "snippet": {"title": title[:150], "description": description[:5000]},
                "status": {"privacyStatus": "public"},
            },
        ).execute()
        return resp["id"]
    except Exception as e:
        print(f"  playlist create fail ({title[:40]}): {e}")
        return None


def _existing_items(youtube: Any, playlist_id: str) -> set[str]:
    ids: set[str] = set()
    next_page = None
    while True:
        req = youtube.playlistItems().list(
            part="contentDetails", playlistId=playlist_id,
            maxResults=50, pageToken=next_page,
        )
        resp = req.execute()
        for it in resp.get("items", []):
            ids.add(it["contentDetails"]["videoId"])
        next_page = resp.get("nextPageToken")
        if not next_page:
            break
    return ids


def _add_to_playlist(youtube: Any, playlist_id: str, video_id: str) -> bool:
    try:
        youtube.playlistItems().insert(
            part="snippet",
            body={"snippet": {"playlistId": playlist_id,
                                "resourceId": {"kind": "youtube#video",
                                                "videoId": video_id}}},
        ).execute()
        return True
    except Exception as e:
        print(f"  playlist add {video_id} fail: {e}")
        return False


def refresh_channel(yt_prefix: str) -> dict[str, Any]:
    """Refresca playlists de un canal. yt_prefix='' → default WaitWhy."""
    playlists_map = CHANNEL_PLAYLISTS.get(yt_prefix)
    if not playlists_map:
        return {"status": "no_config", "prefix": yt_prefix}

    prev_prefix = os.environ.get("YT_CHANNEL_PREFIX", "")
    if yt_prefix:
        os.environ["YT_CHANNEL_PREFIX"] = yt_prefix
    else:
        os.environ.pop("YT_CHANNEL_PREFIX", None)

    try:
        creds = _get_credentials()
        youtube = googleapiclient.discovery.build("youtube", "v3", credentials=creds)
        uploads = _list_uploads(youtube, max_results=50)
        if not uploads:
            return {"status": "no_uploads", "prefix": yt_prefix}

        ledger = _load_ledger()
        ledger_ch = ledger.setdefault(yt_prefix, {})
        summary: dict[str, dict] = {}

        for pl_title, keywords in playlists_map.items():
            kws = [k.lower() for k in keywords]
            matching = [
                v for v in uploads
                if any(k in v["title"].lower() for k in kws)
            ]
            if len(matching) < 3:
                continue  # No vale la pena playlist con <3 items
            pid = _ensure_playlist(
                youtube, ledger_ch, pl_title,
                f"Vídeos del canal agrupados: {pl_title}. "
                f"Actualizado automáticamente.",
            )
            if not pid:
                continue
            ledger_ch[pl_title] = pid
            existing = _existing_items(youtube, pid)
            added = 0
            for v in matching:
                if v["id"] in existing:
                    continue
                if _add_to_playlist(youtube, pid, v["id"]):
                    added += 1
            summary[pl_title] = {
                "playlist_id": pid, "matched": len(matching),
                "existing": len(existing), "added": added,
            }
            print(f"  ✓ '{pl_title}' matched={len(matching)} +{added}")

        _save_ledger(ledger)
        return {"status": "ok", "prefix": yt_prefix, "summary": summary}
    except Exception as e:
        return {"status": "error", "prefix": yt_prefix, "error": str(e)[:200]}
    finally:
        if prev_prefix:
            os.environ["YT_CHANNEL_PREFIX"] = prev_prefix
        else:
            os.environ.pop("YT_CHANNEL_PREFIX", None)


def refresh_all() -> dict[str, Any]:
    """Refresca playlists de todos los canales configurados."""
    results: dict[str, Any] = {}
    for prefix in CHANNEL_PLAYLISTS.keys():
        label = prefix or "YT_MAIN"
        print(f"\n─── {label} ───")
        results[label] = refresh_channel(prefix)
    return results
