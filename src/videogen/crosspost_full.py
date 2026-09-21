"""Helper unificado de crossposting Short → Bluesky + Mastodon + Threads + Instagram.

Historia: 15/09/26 se detectó que 4 canales (ambient/MenteEnCalma,
TopRanking ES, rankings_en, ai_tools EN) NO postean a Instagram Reels
porque cada pipeline tenía su propio crosspost incompleto. User quiere
TODOS los shorts publicados en @waitwhy_ (cuenta IG unificada).

21/09/26: filtro IG por whitelist (deep research reveló que @waitwhy_
recibe 15 nichos mezclados → Originality Score bajo → penalty -40-80%
reach). Ahora solo canales AFINES a true crime ES publican a IG.

Este módulo centraliza el flujo — cualquier pipeline nuevo que suba un
Short debe llamar `crosspost_short(...)` tras el upload YT y ya está.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


# Whitelist canales AFINES a @waitwhy_ IG (true crime / legal / hist ES).
# Los canales NO listados aquí NO publican a IG (evita mezcla temática que
# tira Originality Score). Match por prefix del channel_label.
IG_WHITELIST_PREFIXES = (
    "waitwhy",       # true crime ES principal
    "criminopatia",  # true crime forense ES → afín
    "legal",         # derecho ES → afín (contratos, casos judicial)
    "ayudas",        # gob ES → semi-afín (público overlap)
    "pov",           # historia ES narrativa → semi-afín
    "trabajos",      # laboral (redirige a legal) → afín
)


def _ig_allowed(channel_label: str) -> bool:
    """True si este canal puede publicar a IG (whitelist true crime ES)."""
    cl = (channel_label or "").lower().strip()
    return any(cl.startswith(p) for p in IG_WHITELIST_PREFIXES)


def crosspost_short(dst_dir: Path, title: str, yt_url: str,
                     teaser: str = "", channel_label: str = "canal") -> dict[str, bool]:
    """Postea a Bluesky + Mastodon + Threads + Instagram (best-effort).

    Cada error se aísla — un fallo en una plataforma no rompe las demás.
    IG requiere que `dst_dir / video_es_vertical.mp4` (o video_en_vertical.mp4
    para canales EN) exista para hacer upload real; sin mp4 → skip IG.

    Devuelve dict con emoji plataforma → bool éxito, para notif Telegram.
    """
    result: dict[str, bool] = {}
    slug = dst_dir.name if isinstance(dst_dir, Path) else str(dst_dir)

    # 1) Bluesky
    try:
        from . import bluesky_poster
        r = bluesky_poster.post_short_to_bluesky(title, yt_url, teaser=teaser)
        result["🦋"] = bool(r)
    except Exception as e:
        print(f"  {channel_label} bluesky fail: {e}")
        result["🦋"] = False

    # 2) Mastodon
    try:
        from . import mastodon_poster
        r = mastodon_poster.post_short_to_mastodon(title, yt_url, teaser=teaser)
        result["🐘"] = bool(r)
    except Exception as e:
        print(f"  {channel_label} mastodon fail: {e}")
        result["🐘"] = False

    # 3) Threads
    try:
        from . import threads_poster
        r = threads_poster.post_short_to_threads(title, yt_url, teaser=teaser)
        result["🧵"] = bool(r and not (isinstance(r, dict) and r.get("dry_run")))
    except Exception as e:
        print(f"  {channel_label} threads fail: {e}")
        result["🧵"] = False

    # 4) Instagram Reels — SOLO canales afines a @waitwhy_ (whitelist).
    # Deep research 21/09 confirmó -40-80% reach por mezcla temática si
    # subimos canales no afines (padel/motor/IA/fractales/tax/rankings).
    if not _ig_allowed(channel_label):
        print(f"  {channel_label} ig: SKIP (no en whitelist true crime ES)")
        result["📸"] = False
    else:
        try:
            from . import instagram_poster
            mp4: Path | None = None
            if isinstance(dst_dir, Path) and dst_dir.exists():
                for lang in ("es", "en"):
                    p = dst_dir / f"video_{lang}_vertical.mp4"
                    if p.exists():
                        mp4 = p
                        break
            if mp4:
                r = instagram_poster.post_reel_to_instagram(
                    title, yt_url, mp4, slug, teaser=teaser
                )
                result["📸"] = bool(r)
            else:
                print(f"  {channel_label} ig: no mp4 vertical en {dst_dir}")
                result["📸"] = False
        except Exception as e:
            print(f"  {channel_label} ig fail: {e}")
            result["📸"] = False

    return result


def crosspost_short_from_mp4(mp4_path: Path, title: str, yt_url: str,
                              teaser: str = "", channel_label: str = "canal",
                              slug: str | None = None) -> dict[str, bool]:
    """Variante para pipelines que solo tienen la ruta al mp4 sin dst_dir.

    Ambient/MenteEnCalma genera el mp4 fuera de output/{pending,uploaded}/{slug}/,
    así que llamamos aquí con la ruta directa.
    """
    result: dict[str, bool] = {}
    slug = slug or (mp4_path.stem if isinstance(mp4_path, Path) else "short")

    try:
        from . import bluesky_poster
        r = bluesky_poster.post_short_to_bluesky(title, yt_url, teaser=teaser)
        result["🦋"] = bool(r)
    except Exception as e:
        print(f"  {channel_label} bluesky fail: {e}"); result["🦋"] = False

    try:
        from . import mastodon_poster
        r = mastodon_poster.post_short_to_mastodon(title, yt_url, teaser=teaser)
        result["🐘"] = bool(r)
    except Exception as e:
        print(f"  {channel_label} mastodon fail: {e}"); result["🐘"] = False

    try:
        from . import threads_poster
        r = threads_poster.post_short_to_threads(title, yt_url, teaser=teaser)
        result["🧵"] = bool(r and not (isinstance(r, dict) and r.get("dry_run")))
    except Exception as e:
        print(f"  {channel_label} threads fail: {e}"); result["🧵"] = False

    # IG whitelist true crime ES — canales fuera del nicho NO publican
    if not _ig_allowed(channel_label):
        print(f"  {channel_label} ig: SKIP (no en whitelist true crime ES)")
        result["📸"] = False
    else:
        try:
            from . import instagram_poster
            if mp4_path and Path(mp4_path).exists():
                r = instagram_poster.post_reel_to_instagram(
                    title, yt_url, Path(mp4_path), slug, teaser=teaser
                )
                result["📸"] = bool(r)
            else:
                print(f"  {channel_label} ig: mp4 no existe {mp4_path}")
                result["📸"] = False
        except Exception as e:
            print(f"  {channel_label} ig fail: {e}"); result["📸"] = False

    return result


def summary_line(result: dict[str, bool]) -> str:
    """Formato compacto para notif Telegram: '🦋✅ · 🐘✅ · 🧵❌ · 📸✅'."""
    return " · ".join(f"{k}{'✅' if v else '❌'}" for k, v in result.items())
