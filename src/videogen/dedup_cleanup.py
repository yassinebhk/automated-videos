"""Limpieza de duplicados de bajo alcance en YouTube → set PRIVATE (reversible).

NO borra (irreversible). Pone en PRIVADO las COPIAS duplicadas con casi nada de
audiencia (views < umbral), conservando SIEMPRE la copia con más views de cada
grupo. Quita el ruido del canal y del algoritmo, pero es 100% reversible (se puede
volver a público desde YouTube Studio o con --restore).

Petición usuario 28/09: "eliminar de las rrss los videos duplicados... solo si
vemos que no han tenido apenas audiencia y hacen ruido". Elegimos set-private en
vez de delete por respetar el principio de no hacer cosas irreversibles sin
necesidad. Ver [[dedup-semantico-titulo]].

Requiere scope `youtube.force-ssl` en el refresh token del canal (ya está en
upload_youtube.SCOPES del consent). Si un token no lo tiene → 403
insufficientPermissions → se reporta ese canal para reauth y NO rompe el resto.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path

from .config import ROOT
from . import dedup_common

STATS_HISTORY = ROOT / "output" / "stats_history.jsonl"
DEFAULT_MAX_VIEWS = 30
MIN_NORM_LEN = 8  # ignora títulos demasiado cortos (falsos positivos de agrupación)


def _prefix_for_platform_key(pk: str) -> str:
    """youtube_tax → YT_TAX · youtube → '' (canal principal WaitWhy)."""
    if pk == "youtube":
        return ""
    return "YT_" + pk[len("youtube_"):].upper()


def find_duplicate_lowview(max_views: int = DEFAULT_MAX_VIEWS,
                           history_path: Path = STATS_HISTORY) -> dict[str, list[dict]]:
    """Agrupa vídeos YT por (canal, título normalizado). Para cada grupo con ≥2
    copias, CONSERVA la de más views y marca las demás con views < max_views como
    candidatas a privar. Devuelve {platform_key: [ {video_id,title,views,keep_views,keep_id} ]}.
    """
    if not history_path.exists():
        return {}
    last: dict[str, tuple] = {}  # vid -> (ts, views, title, pk)
    for line in history_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("kind") != "video":
            continue
        pk = r.get("platform", "") or ""
        vid = r.get("video_id")
        title = r.get("title") or ""
        if not (pk.startswith("youtube") and vid and title):
            continue
        ts = r.get("ts", 0) or 0
        views = r.get("views", 0) or 0
        if vid not in last or ts >= last[vid][0]:
            last[vid] = (ts, views, title, pk)

    groups: dict[tuple, list[tuple]] = defaultdict(list)
    for vid, (ts, views, title, pk) in last.items():
        n = dedup_common.norm_title(title)
        if len(n) >= MIN_NORM_LEN:
            groups[(pk, n)].append((vid, views, title))

    out: dict[str, list[dict]] = defaultdict(list)
    for (pk, n), items in groups.items():
        if len(items) < 2:
            continue
        items.sort(key=lambda x: -x[1])  # más views primero
        keep_id, keep_views, _ = items[0]
        for vid, views, title in items[1:]:
            if views < max_views:
                out[pk].append({
                    "video_id": vid, "title": title, "views": views,
                    "keep_views": keep_views, "keep_id": keep_id,
                })
    return dict(out)


def _build_service(prefix: str):
    import googleapiclient.discovery
    from .upload_youtube import _get_credentials
    creds = _get_credentials()  # usa YT_CHANNEL_PREFIX ya seteado por el caller
    return googleapiclient.discovery.build(
        "youtube", "v3", credentials=creds, cache_discovery=False)


def _apply_privacy(prefix: str, video_ids: list[str], target: str) -> tuple[list, list]:
    """Cambia privacyStatus de una lista de vídeos en el canal `prefix`.
    target: 'private' (ocultar) o 'public' (restaurar). Devuelve (ok, failed)."""
    prev = os.environ.get("YT_CHANNEL_PREFIX")
    if prefix:
        os.environ["YT_CHANNEL_PREFIX"] = prefix
    else:
        os.environ.pop("YT_CHANNEL_PREFIX", None)
    ok: list[str] = []
    failed: list[tuple[str, str]] = []
    try:
        try:
            yt = _build_service(prefix)
        except Exception as e:
            # Sin token / token en cuenta equivocada → todo el canal falla, aislado.
            return [], [(v, f"creds: {type(e).__name__}: {str(e)[:100]}") for v in video_ids]
        for vid in video_ids:
            try:
                cur = yt.videos().list(part="status", id=vid).execute().get("items", [])
                if not cur:
                    failed.append((vid, "not_found"))
                    continue
                st = cur[0]["status"]
                if st.get("privacyStatus") == target:
                    ok.append(vid)  # ya estaba como se quería
                    continue
                st["privacyStatus"] = target
                # videos.update reemplaza el part enviado → reenviamos el status completo
                yt.videos().update(part="status", body={"id": vid, "status": st}).execute()
                ok.append(vid)
            except Exception as e:
                failed.append((vid, f"{type(e).__name__}: {str(e)[:140]}"))
    finally:
        if prev is not None:
            os.environ["YT_CHANNEL_PREFIX"] = prev
        else:
            os.environ.pop("YT_CHANNEL_PREFIX", None)
    return ok, failed


def run(apply: bool = False, max_views: int = DEFAULT_MAX_VIEWS,
        only_prefix: str | None = None, restore: bool = False) -> dict:
    """Dry-run (default) o --apply. restore=True vuelve a público (deshacer)."""
    cands = find_duplicate_lowview(max_views)
    if only_prefix is not None:
        want = only_prefix.strip()
        cands = {pk: v for pk, v in cands.items()
                 if _prefix_for_platform_key(pk) == want or pk == want}

    total = sum(len(v) for v in cands.values())
    total_views = sum(c["views"] for v in cands.values() for c in v)
    target = "public" if restore else "private"
    action = "RESTAURAR a público" if restore else "poner en PRIVADO"

    print(f"=== dedup-cleanup · {'APPLY' if apply else 'DRY-RUN'} · {action} "
          f"· umbral views<{max_views} ===")
    print(f"Candidatas: {total} copias duplicadas · {total_views} views combinadas "
          f"(conservo la mejor de cada grupo)\n")
    for pk in sorted(cands, key=lambda p: -len(cands[p])):
        items = cands[pk]
        pref = _prefix_for_platform_key(pk) or "(principal/WaitWhy)"
        print(f"  {pk:20} [{pref}] · {len(items)} copias · "
              f"{sum(c['views'] for c in items)} views")

    result = {"total": total, "total_views": total_views, "by_channel": {},
              "applied": apply, "target": target}
    if not apply:
        print("\n(dry-run — no se ha tocado nada. Añade --apply para ejecutar.)")
        result["candidates"] = {pk: [c["video_id"] for c in v] for pk, v in cands.items()}
        return result

    print(f"\n--- Ejecutando ({action}) ---")
    tot_ok = 0
    scope_fail_channels = []
    for pk, items in cands.items():
        prefix = _prefix_for_platform_key(pk)
        vids = [c["video_id"] for c in items]
        ok, failed = _apply_privacy(prefix, vids, target)
        tot_ok += len(ok)
        result["by_channel"][pk] = {"ok": len(ok), "failed": failed}
        note = ""
        if failed:
            joined = " ".join(f for _, f in failed).lower()
            if "insufficient" in joined or "forbidden" in joined or "403" in joined or "creds" in joined:
                scope_fail_channels.append(prefix or "(principal)")
                note = " ⚠️ posible falta de scope force-ssl / reauth"
        print(f"  {pk:20} ok={len(ok)} fail={len(failed)}{note}")
    print(f"\nTotal {action}: {tot_ok}/{total}")
    if scope_fail_channels:
        print("\n⚠️ Canales que fallaron (probable reauth con force-ssl): "
              + ", ".join(sorted(set(scope_fail_channels))))
    result["scope_fail_channels"] = sorted(set(scope_fail_channels))
    result["applied_ok"] = tot_ok
    return result
