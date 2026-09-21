"""Dashboard de control multi-canal — agrega TODAS las métricas reales del sistema
(YouTube, IG, TikTok, Bluesky, Mastodon, Threads) en un único `docs/dashboard/data.json`
que consume la UI en `docs/dashboard/index.html` (GitHub Pages, coste cero).

Fuentes de verdad (100% datos reales, sin inventar nada):
  - output/stats_history.jsonl   → series temporales subs/views/likes por canal + top/peor vídeos
  - output/ig_publish_log.json   → ratio de éxito real de subidas a Instagram
  - output/social_boost_log.json → cobertura de cross-post (Bluesky/Mastodon/Threads)
  - .github/workflows/*.yml       → cron de cada canal → agenda (lista + calendario)

Se ejecuta con:  videogen dashboard
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
    _MADRID = ZoneInfo("Europe/Madrid")
except Exception:  # pragma: no cover
    _MADRID = timezone(timedelta(hours=2))

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "output"
DOCS = ROOT / "docs"
WORKFLOWS = ROOT / ".github" / "workflows"
PAGES_BASE = "https://yassinebhk.github.io/automated-videos"

# ── Registro de canales: única fuente de verdad para nombres/handles/estado ──
# platform_key  = clave usada en stats_history.jsonl (None si aún no se snapshotea)
# category      = nicho para agrupar y analizar temas
# status        = active | paused  (6 pausados en la consolidación 18/09)
CH_COLORS = [
    "#ff5470", "#4cc9f0", "#f7b801", "#7ae582", "#b388ff",
    "#ff9770", "#00bbf9", "#c5e063", "#f15bb5", "#9bf6ff",
    "#ffd6a5", "#a0c4ff", "#ffadad", "#caffbf", "#bdb2ff",
]

# group="core" = los 10 canales YouTube reales del usuario; "extra" = líneas de
# contenido / experimentales (sin canal YT dedicado o en evaluación).
CHANNELS: list[dict] = [
    dict(key="waitwhy",    name="WaitWhy",           pk="youtube",          handle="@waitwhy_ybb",     cat="True crime / corrupción", status="active", lang="ES", group="core", flagship=True),
    dict(key="ayudas",     name="AyudaGob",          pk="youtube_ayudas",   handle="@AyudaGob_es",     cat="Ayudas y subvenciones",   status="active", lang="ES", group="core"),
    dict(key="motor",      name="Motor60s",          pk="youtube_motor",    handle="@Motor60sES",      cat="Motor / curiosidades",    status="active", lang="ES", group="core"),
    dict(key="pov",        name="TiempoAtrás ES",    pk="youtube_pov",      handle="@TiempoAtras_ES",  cat="Historia / POV",          status="active", lang="ES", group="core"),
    dict(key="ranking",    name="TopRanking ES",     pk="youtube_ranking",  handle="@TopRanking_ES",   cat="Rankings / datos",        status="active", lang="ES", group="core"),
    dict(key="ia",         name="IA Autónomos ES",   pk="youtube_ia",       handle="@IAAutonomos_es",  cat="IA para autónomos",       status="active", lang="ES", group="core"),
    dict(key="aitools",    name="AI Tools Weekly",   pk="youtube_aitools",  handle=None,               cat="AI tools",                status="active", lang="EN", group="core"),
    dict(key="tax",        name="TaxHack ES",        pk="youtube_tax",      handle="@TaxHack_es",      cat="Fiscalidad",              status="active", lang="ES", group="core"),
    dict(key="legal",      name="TusDerechos ES",    pk="youtube_legal",    handle="@TusDerechos_ES",  cat="Derecho laboral",         status="active", lang="ES", group="core"),
    dict(key="ambient",    name="MenteEnCalma",      pk="youtube_ambient",  handle=None,               cat="Relax / binaural",        status="active", lang="ES", group="core"),
    dict(key="padel",      name="Pádel",             pk=None,               handle=None,               cat="Pádel (Manim)",           status="active", lang="ES", group="extra"),
    dict(key="satisfying", name="Infinite Fractals", pk=None,               handle=None,               cat="Satisfying / hipnótico",  status="active", lang="EN", group="extra"),
    dict(key="trabajos",   name="CuriosLaboral ES",  pk=None,               handle="@CuriosLaboral_ES",cat="Curiosidades laborales",  status="paused", lang="ES", group="extra"),
    dict(key="criminopatia", name="Criminopatía",    pk=None,               handle="@Criminopatia_ES", cat="Criminología",            status="paused", lang="ES", group="extra"),
    dict(key="rankings_en", name="Global Rankings",  pk=None,               handle=None,               cat="Rankings (EN)",           status="paused", lang="EN", group="extra"),
]

# IG whitelist (otra sesión 21/09): solo canales afines a true crime ES suben a
# Instagram @waitwhy_ (evita penalty de Originality Score por mezcla de nichos).
IG_WHITELIST = {"waitwhy", "criminopatia", "legal", "ayudas", "pov", "trabajos"}
# Canales huérfanos (sin YT propio) que suben al canal host de otro nicho afín.
YT_HOST_REDIRECT = {"criminopatia": "WaitWhy", "trabajos": "TusDerechos ES", "padel": "TopRanking ES"}

# Plataformas sociales (no-YouTube) y su handle/URL de perfil
SOCIALS: list[dict] = [
    dict(pk="tiktok",    name="TikTok",    handle="@interest_stuff", url="https://tiktok.com/@interest_stuff", color="#00f2ea"),
    dict(pk="instagram", name="Instagram", handle=None,              url=None,                                 color="#e1306c"),
    dict(pk="bluesky",   name="Bluesky",   handle=None,              url="https://bsky.app",                   color="#0a7aff"),
    dict(pk="mastodon",  name="Mastodon",  handle=None,              url=None,                                 color="#6364ff"),
    dict(pk="threads",   name="Threads",   handle=None,              url="https://threads.net",                color="#a1a1aa"),
]

# workflow → (nombre legible, canal, categoría de agenda)
SCHEDULE_MAP: dict[str, tuple[str, str, str]] = {
    "daily-short":            ("WaitWhy · Short",        "WaitWhy",          "content"),
    "daily-short-afternoon":  ("WaitWhy · Short (tarde)", "WaitWhy",         "content"),
    "tax-daily":              ("TaxHack · Short",        "TaxHack ES",       "content"),
    "legal-daily":            ("TusDerechos · Short",    "TusDerechos ES",   "content"),
    "ayudas-daily":           ("AyudaGob · Short",       "AyudaGob",         "content"),
    "motor-daily":            ("Motor60s · Short",       "Motor60s",         "content"),
    "pov-daily":              ("TiempoAtrás · Short",    "TiempoAtrás ES",   "content"),
    "ranking-daily":          ("TopRanking · Short",     "TopRanking ES",    "content"),
    "trabajos-daily":         ("CuriosLaboral · Short",  "CuriosLaboral ES", "content"),
    "criminopatia-daily":     ("Criminopatía · Short",   "Criminopatía",     "content"),
    "ia-autonomos-daily":     ("IA Autónomos · Short",   "IA Autónomos ES",  "content"),
    "ai-tools-daily":         ("AI Tools · Short",       "AI Tools Weekly",  "content"),
    "rankings-en-daily":      ("Global Rankings · Short", "Global Rankings", "content"),
    "padel-daily":            ("Pádel · Vídeo",          "Pádel",            "content"),
    "satisfying-daily":       ("Infinite Fractals",      "Infinite Fractals", "content"),
    "ambient-short-daily":    ("MenteEnCalma · Short",   "MenteEnCalma",     "content"),
    "ambient-daily":          ("MenteEnCalma · Long-form", "MenteEnCalma",   "longform"),
    "tax-longform-weekly":    ("TaxHack · Long-form",    "TaxHack ES",       "longform"),
    "legal-longform-weekly":  ("TusDerechos · Long-form", "TusDerechos ES",  "longform"),
    "ayudas-longform-weekly": ("AyudaGob · Long-form",   "AyudaGob",         "longform"),
    "motor-longform-weekly":  ("Motor60s · Long-form",   "Motor60s",         "longform"),
    "ai-tools-longform-weekly": ("AI Tools · Long-form", "AI Tools Weekly",  "longform"),
    "pov-longform-weekly":    ("TiempoAtrás · Long-form", "TiempoAtrás ES",  "longform"),
    "ia-autonomos-longform-weekly": ("IA Autónomos · Long-form", "IA Autónomos ES", "longform"),
    "ranking-longform-weekly": ("TopRanking · Long-form",  "TopRanking ES",    "longform"),
    "weekly-longform":        ("WaitWhy · Long-form",    "WaitWhy",          "longform"),
    "social-boost":           ("Cross-post redes",       "Todos",            "social"),
    "bluesky-growth":         ("Bluesky · growth",       "Bluesky",          "social"),
    "mastodon-growth":        ("Mastodon · growth",      "Mastodon",         "social"),
    "x-growth":               ("X · growth",             "X",                "social"),
    "narrative-post":         ("Narrativa (Threads/IG)", "Todos",            "social"),
    "narrative-post-bluesky": ("Narrativa (Bluesky)",    "Bluesky",          "social"),
    "community-poll":         ("Encuesta comunidad",     "WaitWhy",          "social"),
    "daily-summary":          ("Resumen diario",         "Ops",              "ops"),
    "healthcheck":            ("Health-check",           "Ops",              "ops"),
    "ig-status-daily":        ("IG status",              "Ops",              "ops"),
    "first-comment-catchup":  ("1er comentario",         "Ops",              "ops"),
    "catchup-all-channels":   ("Catch-up canales",       "Ops",              "ops"),
}

_STOP = set("""de la el en y a los las un una para con que del por su al se es lo como más
o si me te ni entre sin sobre este esta estos shorts short the a an of to in for you your
how why what when top con qué cómo cuánto cuánta este cada muy tras cuando donde vs""".split())


# ─────────────────────────── helpers ───────────────────────────
def _read_history() -> list[dict]:
    p = OUTPUT / "stats_history.jsonl"
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out


def _latest_per(records: list[dict], key: str) -> dict[str, dict]:
    """Último registro (mayor ts) por valor de `key`."""
    best: dict[str, dict] = {}
    for r in records:
        k = r.get(key)
        if k is None:
            continue
        if k not in best or (r.get("ts", 0) or 0) > (best[k].get("ts", 0) or 0):
            best[k] = r
    return best


def _strip_html(s: str) -> str:
    """Quita etiquetas HTML (Mastodon/Bluesky guardan <p>…</p>) y colapsa espacios."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()


def _video_url(platform: str, vid: str) -> str | None:
    if not vid:
        return None
    if platform == "youtube" or platform.startswith("youtube_"):
        return f"https://www.youtube.com/watch?v={vid}"
    if platform == "tiktok":
        return f"https://www.tiktok.com/@interest_stuff/video/{vid}"
    return None


def _yt_url(handle: str | None) -> str | None:
    return f"https://www.youtube.com/{handle}" if handle else None


def _channel_series(chan_recs: list[dict]) -> list[dict]:
    """Un punto por día (último snapshot del día) con subs/views."""
    by_day: dict[str, dict] = {}
    for r in sorted(chan_recs, key=lambda x: x.get("ts", 0) or 0):
        d = r.get("date")
        if not d:
            continue
        by_day[d] = {"date": d, "subs": r.get("subs", 0) or 0, "views": r.get("views", 0) or 0}
    return list(by_day.values())


def _merge_ff(series_list: list[list[dict]], fields=("subs", "views")) -> list[dict]:
    """Suma varias series por día con forward-fill: cada canal aporta su último valor
    conocido a partir de su primera fecha (0 antes). Da una curva de red suave y real."""
    all_dates = sorted({p["date"] for s in series_list for p in s})
    if not all_dates:
        return []
    out = []
    idx = [0] * len(series_list)
    last = [{f: 0 for f in fields} for _ in series_list]
    started = [False] * len(series_list)
    for d in all_dates:
        agg = {f: 0 for f in fields}
        for i, s in enumerate(series_list):
            while idx[i] < len(s) and s[idx[i]]["date"] <= d:
                last[i] = s[idx[i]]; started[i] = True; idx[i] += 1
            if started[i]:
                for f in fields:
                    agg[f] += last[i].get(f, 0) or 0
        out.append({"date": d, **agg})
    return out


def _delta(series: list[dict], field: str, days: int) -> int | None:
    """Diferencia del campo entre el último punto y el punto de hace ~`days`."""
    if not series:
        return None
    last = series[-1]
    try:
        last_d = datetime.strptime(last["date"], "%Y-%m-%d").date()
    except Exception:
        return None
    target = last_d - timedelta(days=days)
    prev = None
    for pt in series:
        try:
            pd = datetime.strptime(pt["date"], "%Y-%m-%d").date()
        except Exception:
            continue
        if pd <= target:
            prev = pt
        else:
            break
    if prev is None:
        prev = series[0]
    return (last.get(field, 0) or 0) - (prev.get(field, 0) or 0)


# ─────────────────────────── cron / agenda ───────────────────────────
def _parse_crons() -> list[dict]:
    """Lee el cron de cada workflow relevante → lista de definiciones recurrentes."""
    out = []
    if not WORKFLOWS.exists():
        return out
    for wf in sorted(WORKFLOWS.glob("*.yml")):
        stem = wf.name[:-4]
        meta = SCHEDULE_MAP.get(stem)
        if not meta:
            continue
        name, channel, cat = meta
        txt = wf.read_text(encoding="utf-8", errors="ignore")
        crons = re.findall(r"cron:\s*['\"]?([0-9*,/ ]+?)['\"]?\s*(?:#|$)", txt, re.M)
        for expr in crons:
            parts = expr.split()
            if len(parts) != 5:
                continue
            mn, hr, dom, mon, dow = parts
            out.append(dict(workflow=stem, name=name, channel=channel, category=cat,
                            cron=expr.strip(), minute=mn, hour=hr, dow=dow))
    return out


def _matches(field: str, value: int) -> bool:
    if field == "*":
        return True
    parts = set()
    for chunk in field.split(","):
        chunk = chunk.strip()
        if "/" in chunk:            # step, ej */2
            base, step = chunk.split("/")
            step = int(step)
            rng = range(0, 60) if value < 60 else range(0, 60)
            for v in range(0, 60):
                if v % step == 0:
                    parts.add(v)
            continue
        try:
            parts.add(int(chunk))
        except ValueError:
            pass
    return value in parts


def _expand_upcoming(cron_defs: list[dict], days: int = 14) -> list[dict]:
    """Próximas ocurrencias (UTC) en los siguientes `days` días → orden cronológico."""
    now = datetime.now(timezone.utc)
    out = []
    for d in range(days):
        day = (now + timedelta(days=d)).date()
        dow = (day.weekday() + 1) % 7   # cron: 0=domingo … 6=sábado
        for cd in cron_defs:
            try:
                hrs = [int(x) for x in cd["hour"].split(",") if x.strip().isdigit()]
                mns = [int(x) for x in cd["minute"].split(",") if x.strip().isdigit()]
            except Exception:
                continue
            if not hrs or not mns:
                continue
            if not _matches(cd["dow"], dow):
                continue
            for hr in hrs:
                for mn in mns:
                    dt_utc = datetime(day.year, day.month, day.day, hr, mn, tzinfo=timezone.utc)
                    if dt_utc < now:
                        continue
                    dt_local = dt_utc.astimezone(_MADRID)
                    out.append(dict(
                        ts=dt_utc.isoformat(),
                        local=dt_local.strftime("%Y-%m-%d %H:%M"),
                        date=dt_local.strftime("%Y-%m-%d"),
                        time=dt_local.strftime("%H:%M"),
                        name=cd["name"], channel=cd["channel"], category=cd["category"],
                    ))
    out.sort(key=lambda x: x["ts"])
    return out


# ─────────────────────────── build ───────────────────────────
def build() -> dict:
    recs = _read_history()
    video_recs = [r for r in recs if r.get("kind") == "video"]
    chan_recs = [r for r in recs if r.get("kind") == "channel"]

    dates = sorted({r["date"] for r in recs if r.get("date")})
    rng = dict(first=dates[0] if dates else None,
               last=dates[-1] if dates else None,
               days=len(dates))

    # snapshots de canal por plataforma
    chan_by_pk: dict[str, list[dict]] = defaultdict(list)
    for r in chan_recs:
        chan_by_pk[r["platform"]].append(r)
    vids_by_pk: dict[str, list[dict]] = defaultdict(list)
    for r in video_recs:
        vids_by_pk[r["platform"]].append(r)

    # primera fecha/hora en que se vio cada vídeo ≈ momento de publicación
    first_date_by_vid: dict[str, str] = {}
    first_ts_by_vid: dict[str, int] = {}
    for r in sorted(video_recs, key=lambda x: x.get("ts", 0) or 0):
        vid = r.get("video_id")
        if not vid:
            continue
        if vid not in first_date_by_vid and r.get("date"):
            first_date_by_vid[vid] = r["date"]
        if vid not in first_ts_by_vid and r.get("ts"):
            first_ts_by_vid[vid] = r["ts"]

    today = datetime.now(_MADRID).date()

    def _days_since(d: str | None) -> int | None:
        if not d:
            return None
        try:
            return (today - datetime.strptime(d, "%Y-%m-%d").date()).days
        except Exception:
            return None

    def _weekday_hist(vids) -> list[int]:
        h = [0] * 7  # lunes..domingo
        for v in vids:
            d = first_date_by_vid.get(v)
            if not d:
                continue
            try:
                h[datetime.strptime(d, "%Y-%m-%d").date().weekday()] += 1
            except Exception:
                pass
        return h

    global_weekday = [0] * 7

    # ── canales YouTube ──
    channels_out = []
    net_subs = net_views = net_videos = 0
    kw_stats: dict[str, list[int]] = defaultdict(list)
    all_videos_flat = []

    for i, ch in enumerate(CHANNELS):
        pk = ch["pk"]
        color = CH_COLORS[i % len(CH_COLORS)]
        series = _channel_series(chan_by_pk.get(pk, [])) if pk else []
        latest = series[-1] if series else {}
        subs = latest.get("subs", 0)
        views = latest.get("views", 0)
        # nº vídeos: del último snapshot que lo traiga, o distinct video_ids
        videos = 0
        for r in sorted(chan_by_pk.get(pk, []), key=lambda x: x.get("ts", 0) or 0):
            if r.get("videos"):
                videos = r["videos"]
        if not videos and pk:
            videos = len({r.get("video_id") for r in vids_by_pk.get(pk, []) if r.get("video_id")})

        # top / peor vídeos
        vmap = _latest_per(vids_by_pk.get(pk, []), "video_id") if pk else {}
        vlist = []
        for vid, r in vmap.items():
            title = (r.get("title") or "").strip()
            vv = r.get("views", 0) or 0
            item = dict(video_id=vid, title=title or "(sin título)", views=vv,
                        likes=r.get("likes", 0) or 0, comments=r.get("comments", 0) or 0,
                        date=r.get("date"), url=_video_url(pk, vid))
            vlist.append(item)
            all_videos_flat.append({**item, "channel": ch["name"], "color": color, "cat": ch["cat"]})
            # análisis de temas (solo canales con tracción real)
            if vv > 0 and title:
                for w in re.findall(r"[a-záéíóúñ0-9]{4,}", title.lower()):
                    if w not in _STOP:
                        kw_stats[w].append(vv)
        vlist.sort(key=lambda x: x["views"], reverse=True)
        top_videos = vlist[:8]
        worst_videos = [v for v in reversed(vlist) if v["views"] >= 0][:8]

        # ── métricas ricas por canal ──
        vids_ids = [v["video_id"] for v in vlist]
        likes_total = sum(v["likes"] for v in vlist)
        views_sum = sum(v["views"] for v in vlist)
        eng_rate = round(100 * likes_total / views_sum, 2) if views_sum else None
        views_vals = sorted(v["views"] for v in vlist)
        median_views = views_vals[len(views_vals) // 2] if views_vals else 0
        best_views = views_vals[-1] if views_vals else 0
        first_dates = [first_date_by_vid.get(v) for v in vids_ids if first_date_by_vid.get(v)]
        last_upload = max(first_dates) if first_dates else None
        days_since = _days_since(last_upload)
        _ds = [x for x in (_days_since(d) for d in first_dates) if x is not None]
        vids_7d = sum(1 for x in _ds if x <= 7)
        vids_30d = sum(1 for x in _ds if x <= 30)
        wk = _weekday_hist(vids_ids)
        for i in range(7):
            global_weekday[i] += wk[i]
        # momentum: Δviews últimos 7d vs 7d previos
        d7v = _delta(series, "views", 7)
        d14v = _delta(series, "views", 14)
        prev7v = (d14v - d7v) if (d7v is not None and d14v is not None) else None
        momentum = (d7v - prev7v) if (d7v is not None and prev7v is not None) else None
        # temas del canal
        ch_kw: dict[str, list[int]] = defaultdict(list)
        for v in vlist:
            if v["views"] > 0 and v["title"]:
                for w in re.findall(r"[a-záéíóúñ0-9]{4,}", v["title"].lower()):
                    if w not in _STOP:
                        ch_kw[w].append(v["views"])
        ch_topics = sorted(
            ({"keyword": k, "avg_views": round(sum(vv) / len(vv)), "count": len(vv)}
             for k, vv in ch_kw.items() if len(vv) >= 2),
            key=lambda x: x["avg_views"], reverse=True)[:8]

        if ch["status"] == "active":
            net_subs += subs
            net_views += views
        net_videos += videos

        channels_out.append(dict(
            key=ch["key"], name=ch["name"], handle=ch.get("handle"),
            url=_yt_url(ch.get("handle")), cat=ch["cat"], status=ch["status"],
            lang=ch["lang"], group=ch.get("group", "extra"),
            flagship=ch.get("flagship", False), color=color,
            ig=(ch["key"] in IG_WHITELIST), yt_host=YT_HOST_REDIRECT.get(ch["key"]),
            subs=subs, views=views, videos=videos,
            has_analytics=bool(series),
            likes_total=likes_total, eng_rate=eng_rate,
            median_views=median_views, best_views=best_views,
            vpv=(round(views / videos) if videos else None),
            last_upload=last_upload, days_since=days_since,
            vids_7d=vids_7d, vids_30d=vids_30d,
            per_week=round(vids_30d / 4.3, 1) if vids_30d else 0,
            momentum=momentum, weekday=wk, topics=ch_topics,
            delta7_subs=_delta(series, "subs", 7), delta30_subs=_delta(series, "subs", 30),
            delta7_views=d7v, delta30_views=_delta(series, "views", 30),
            series=series, top_videos=top_videos, worst_videos=worst_videos,
        ))

    # ── plataformas sociales ──
    socials_out = []
    social_followers = 0
    for s in SOCIALS:
        series = _channel_series(chan_by_pk.get(s["pk"], []))
        latest = series[-1] if series else {}
        followers = latest.get("subs", 0)
        social_followers += followers
        vmap = _latest_per(vids_by_pk.get(s["pk"], []), "video_id")
        posts = len(vmap)
        likes = 0
        for r in chan_by_pk.get(s["pk"], []):
            if r.get("likes"):
                likes = max(likes, r.get("likes", 0) or 0)
        # top posts por engagement (views, si no likes, si no comentarios)
        plist = []
        for vid, r in vmap.items():
            plist.append(dict(
                video_id=vid, title=_strip_html(r.get("title") or "") or "(sin texto)",
                views=r.get("views", 0) or 0, likes=r.get("likes", 0) or 0,
                comments=r.get("comments", 0) or 0, date=r.get("date"),
                url=r.get("permalink") or _video_url(s["pk"], vid)))
        plist.sort(key=lambda x: (x["views"], x["likes"], x["comments"]), reverse=True)
        socials_out.append(dict(
            pk=s["pk"], name=s["name"], handle=s.get("handle"), url=s.get("url"),
            color=s["color"], followers=followers, posts=posts, likes=likes,
            delta7=_delta(series, "subs", 7), delta30=_delta(series, "subs", 30),
            series=series, top_posts=plist[:8], recent_posts=sorted(
                plist, key=lambda x: x.get("date") or "", reverse=True)[:8],
        ))

    # ── análisis de temas (mejores / peores) ──
    topics = []
    for w, vs in kw_stats.items():
        if len(vs) < 3:            # requiere señal mínima
            continue
        topics.append(dict(keyword=w, count=len(vs),
                           avg_views=round(sum(vs) / len(vs)),
                           total_views=sum(vs)))
    topics.sort(key=lambda x: x["avg_views"], reverse=True)
    top_topics = topics[:12]
    worst_topics = sorted(topics, key=lambda x: x["avg_views"])[:12]

    all_videos_flat.sort(key=lambda x: x["views"], reverse=True)
    top_overall = all_videos_flat[:12]
    worst_overall = [v for v in reversed(all_videos_flat) if v["views"] >= 0][:12]

    # ── Mejor momento para publicar (día + hora reales, ponderado por views) ──
    DOW_ES = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
    wk_sum = [0] * 7; wk_cnt = [0] * 7
    hr_sum = [0] * 24; hr_cnt = [0] * 24
    for v in all_videos_flat:
        if v["views"] <= 0:
            continue
        vid = v["video_id"]
        d = first_date_by_vid.get(vid)
        if d:
            try:
                wd = datetime.strptime(d, "%Y-%m-%d").weekday()
                wk_sum[wd] += v["views"]; wk_cnt[wd] += 1
            except Exception:
                pass
        ts = first_ts_by_vid.get(vid)
        if ts:
            try:
                h = datetime.fromtimestamp(ts, timezone.utc).astimezone(_MADRID).hour
                hr_sum[h] += v["views"]; hr_cnt[h] += 1
            except Exception:
                pass
    by_weekday = [{"label": DOW_ES[i], "avg": round(wk_sum[i] / wk_cnt[i]) if wk_cnt[i] else 0,
                   "count": wk_cnt[i]} for i in range(7)]
    by_hour = [{"label": f"{i:02d}h", "avg": round(hr_sum[i] / hr_cnt[i]) if hr_cnt[i] else 0,
                "count": hr_cnt[i]} for i in range(24)]
    _bw = max((x for x in by_weekday if x["count"] >= 2), key=lambda x: x["avg"], default=None)
    _bh = max((x for x in by_hour if x["count"] >= 2), key=lambda x: x["avg"], default=None)
    best_time = dict(by_weekday=by_weekday, by_hour=by_hour,
                     best_weekday=_bw["label"] if _bw else None,
                     best_hour=_bh["label"] if _bh else None)

    # ── Ranking por ENGAGEMENT (likes/views), no solo por views ──
    eng_list = []
    for v in all_videos_flat:
        if v["views"] >= 50 and v["likes"] > 0:
            eng_list.append({**v, "eng": round(100 * v["likes"] / v["views"], 2)})
    engagement_top = sorted(eng_list, key=lambda x: x["eng"], reverse=True)[:10]

    # ── Caso de estudio: el vídeo estrella + por qué funcionó (para demo) ──
    case_study = None
    if all_videos_flat:
        cv = all_videos_flat[0]
        kws = [w for w in re.findall(r"[a-záéíóúñ0-9]{4,}", (cv["title"] or "").lower())
               if w not in _STOP][:5]
        case_study = {**cv, "eng": (round(100 * cv["likes"] / cv["views"], 2) if cv["views"] else 0),
                      "keywords": kws}

    # ── Volumen publicado por día (últimos 60 días) ──
    pub_cnt: dict[str, int] = defaultdict(int)
    for vid, d in first_date_by_vid.items():
        pub_cnt[d] += 1
    pub_by_day = [{"date": d, "count": pub_cnt[d]} for d in sorted(pub_cnt)][-60:]

    # ── EN RACHA: vídeos que MÁS views ganan en los últimos ~7 días (de la serie
    #    temporal que vamos acumulando). Lo que está despegando AHORA. ──
    vseries: dict[str, list] = defaultdict(list)
    for r in video_recs:
        pk = str(r.get("platform", ""))
        if pk.startswith("youtube") and r.get("video_id"):
            vseries[r["video_id"]].append((r.get("ts", 0) or 0, r.get("views", 0) or 0))
    meta_by_vid = {v["video_id"]: v for v in all_videos_flat}
    trending = []
    for vid, pts in vseries.items():
        if len(pts) < 2:
            continue
        pts.sort()
        last_ts, last_v = pts[-1]
        target = last_ts - 7 * 86400
        prev = None
        for ts, vv in pts:
            if ts <= target:
                prev = (ts, vv)
        if prev is None:
            prev = pts[0]
        delta = last_v - prev[1]
        if delta > 0:
            m = meta_by_vid.get(vid, {})
            trending.append({"video_id": vid, "title": m.get("title", "(sin título)"),
                             "channel": m.get("channel", ""), "color": m.get("color", "#8a93a6"),
                             "url": m.get("url"), "views": last_v, "delta": delta})
    trending = sorted(trending, key=lambda x: x["delta"], reverse=True)[:10]

    # ── Rendimiento por IDIOMA (ES vs EN) ──
    langmap: dict[str, dict] = {}
    for c in channels_out:
        if c["views"] <= 0:
            continue
        m = langmap.setdefault(c["lang"], {"lang": c["lang"], "channels": 0, "videos": 0,
                                           "views": 0, "subs": 0})
        m["channels"] += 1; m["videos"] += c["videos"]
        m["views"] += c["views"]; m["subs"] += c["subs"]
    by_language = sorted(({**m, "vpv": round(m["views"] / m["videos"]) if m["videos"] else 0}
                          for m in langmap.values()), key=lambda x: x["views"], reverse=True)

    # ── (1) Curva de vistas por vídeo: downsample de la serie a ~16 puntos ──
    def _vspark(vid: str, n: int = 16) -> list[int]:
        pts = sorted(vseries.get(vid, []))
        vals = [v for _ts, v in pts]
        if len(vals) <= n:
            return vals
        step = len(vals) / n
        return [vals[min(len(vals) - 1, int(i * step))] for i in range(n)]
    for v in trending:
        v["spark"] = _vspark(v["video_id"])
    for v in top_overall:
        v["spark"] = _vspark(v["video_id"])

    # ── (5) Interacción: totales de me gusta / comentarios + más comentados ──
    total_likes = sum(v["likes"] for v in all_videos_flat)
    total_comments = sum(v.get("comments", 0) for v in all_videos_flat)
    most_commented = sorted((v for v in all_videos_flat if v.get("comments", 0) > 0),
                            key=lambda x: x["comments"], reverse=True)[:8]
    interaction = dict(likes=total_likes, comments=total_comments,
                       eng_rate=round(100 * total_likes / net_views, 2) if net_views else None,
                       most_commented=most_commented)

    # ── (6) Embudo / alcance estimado ──
    funnel = dict(
        impresiones=net_views,
        interacciones=total_likes + total_comments,
        seguidores=net_subs + social_followers,
        r_interaccion=round(100 * (total_likes + total_comments) / net_views, 2) if net_views else None,
        r_seguidor=round(100 * (net_subs + social_followers) / net_views, 3) if net_views else None,
    )

    # ── Instagram: ratio real de subidas ──
    ig = dict(total=0, ok=0, fail=0, rate=None, recent=[], by_day=[])
    igp = OUTPUT / "ig_publish_log.json"
    if igp.exists():
        try:
            log = json.loads(igp.read_text(encoding="utf-8"))
            if isinstance(log, list):
                # Éxito por VÍDEO: cada vídeo genera varios intentos (fail_container_ready
                # → retry ok). Contar por vídeo (ok si ALGÚN intento salió) refleja la
                # realidad (~100% con R2), no penaliza los reintentos intermedios.
                by_vid: dict[str, str] = {}
                for x in log:
                    key = x.get("slug") or x.get("title") or x.get("ts")
                    if by_vid.get(key) != "ok":
                        by_vid[key] = "ok" if x.get("status") == "ok" else x.get("status")
                vids = len(by_vid)
                ok = sum(1 for v in by_vid.values() if v == "ok")
                fail = vids - ok
                ig["total"] = vids            # vídeos únicos
                ig["attempts"] = len(log)     # intentos brutos (incluye reintentos)
                ig["ok"] = ok
                ig["fail"] = fail
                ig["rate"] = round(100 * ok / vids) if vids else None
                # Ratio RECIENTE (últimos 14 días) — refleja el estado con R2 + retry,
                # sin arrastrar los fallos de la era catbox/litterbox previa.
                cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%d")
                rv: dict[str, str] = {}
                for x in log:
                    if (x.get("ts") or "")[:10] < cutoff:
                        continue
                    key = x.get("slug") or x.get("title") or x.get("ts")
                    if rv.get(key) != "ok":
                        rv[key] = "ok" if x.get("status") == "ok" else x.get("status")
                rok = sum(1 for v in rv.values() if v == "ok")
                ig["total_recent"] = len(rv)
                ig["ok_recent"] = rok
                ig["rate_recent"] = round(100 * rok / len(rv)) if rv else None
                ig["recent"] = [dict(
                    slug=x.get("slug"), title=(x.get("title") or "")[:80],
                    status=x.get("status"), url=x.get("url"),
                    error=(x.get("error") or x.get("error_message") or "")[:120],
                    ts=x.get("ts"),
                ) for x in log[-24:]][::-1]
                day_ok: dict[str, list[int]] = defaultdict(lambda: [0, 0])
                for x in log:
                    ts = (x.get("ts") or "")[:10]
                    if not ts:
                        continue
                    if x.get("status") == "ok":
                        day_ok[ts][0] += 1
                    else:
                        day_ok[ts][1] += 1
                ig["by_day"] = [dict(date=d, ok=v[0], fail=v[1])
                                for d, v in sorted(day_ok.items())]
        except Exception:
            pass

    # ── cross-post (cobertura) ──
    cross = dict(videos=0, bluesky=0, mastodon=0, threads=0)
    sbp = OUTPUT / "social_boost_log.json"
    if sbp.exists():
        try:
            sb = json.loads(sbp.read_text(encoding="utf-8"))
            if isinstance(sb, dict):
                cross["videos"] = len(sb)
                for _vid, plats in sb.items():
                    for p in ("bluesky", "mastodon", "threads"):
                        if p in plats:
                            cross[p] += 1
        except Exception:
            pass

    # ── agenda ──
    name_status = {c["name"]: c["status"] for c in CHANNELS}
    name_color = {c["name"]: CH_COLORS[i % len(CH_COLORS)] for i, c in enumerate(CHANNELS)}
    soc_color = {s["name"]: s["color"] for s in SOCIALS}

    def _tag(item: dict) -> dict:
        ch = item.get("channel", "")
        item["paused"] = name_status.get(ch) == "paused"
        item["color"] = name_color.get(ch) or soc_color.get(ch) or "#8a93a6"
        return item

    cron_defs = _parse_crons()
    upcoming = [_tag(u) for u in _expand_upcoming(cron_defs, days=14)]
    recurring = []
    for cd in cron_defs:
        try:
            hr = int(cd["hour"].split(",")[0]); mn = int(cd["minute"].split(",")[0])
            local = datetime(2026, 1, 5, hr, mn, tzinfo=timezone.utc).astimezone(_MADRID)
            tlabel = local.strftime("%H:%M")
        except Exception:
            tlabel = f"{cd['hour']}:{cd['minute']} UTC"
        dow = cd["dow"]
        days_lbl = "Cada día" if dow == "*" else {
            "0": "Domingo", "1": "Lunes", "2": "Martes", "3": "Miércoles",
            "4": "Jueves", "5": "Viernes", "6": "Sábado",
        }.get(dow, dow)
        recurring.append(_tag(dict(name=cd["name"], channel=cd["channel"],
                              category=cd["category"], time=tlabel,
                              days=days_lbl, cron=cd["cron"])))
    recurring.sort(key=lambda x: (0 if x["category"] == "content" else 1, x["time"]))

    # ── producción esperada (short/long) + salud por canal ──
    prod: dict[str, dict] = {}
    for r in recurring:
        p = prod.setdefault(r["channel"], {"short": False, "long": False,
                                           "short_time": None, "long_time": None, "long_day": None})
        if r["category"] == "content":
            p["short"] = True
            p["short_time"] = r["time"]
        elif r["category"] == "longform":
            p["long"] = True
            p["long_time"] = r["time"]
            p["long_day"] = r["days"]
    for c in channels_out:
        pinfo = prod.get(c["name"], {"short": False, "long": False,
                                     "short_time": None, "long_time": None, "long_day": None})
        c["prod"] = pinfo
        if c["status"] == "paused":
            c["health"] = "pausado"
        elif not c["has_analytics"]:
            c["health"] = "sin_datos"          # activo pero sin histórico de analítica aún
        elif not c["last_upload"]:
            c["health"] = "sin_subidas"
        else:
            ds = c["days_since"] if c["days_since"] is not None else 999
            c["health"] = "al_dia" if ds <= 2 else ("atrasado" if ds <= 7 else "inactivo")
        c["missing_long"] = bool(pinfo["short"] and not pinfo["long"] and c["group"] == "core")

    # histórico: primer día en que apareció cada vídeo → "publicado"
    first_seen: dict[str, dict] = {}
    for r in sorted(video_recs, key=lambda x: x.get("ts", 0) or 0):
        vid = r.get("video_id")
        if not vid or vid in first_seen:
            continue
        pk = r["platform"]
        ch_name = next((c["name"] for c in CHANNELS if c["pk"] == pk),
                       next((s["name"] for s in SOCIALS if s["pk"] == pk), pk))
        first_seen[vid] = dict(date=r.get("date"), platform=pk, channel=ch_name,
                               title=(r.get("title") or "")[:90],
                               url=_video_url(pk, vid), video_id=vid)
    history = sorted(first_seen.values(), key=lambda x: x.get("date") or "", reverse=True)

    # ── KPIs de cabecera ──
    yt_flagship = next((c for c in channels_out if c["key"] == "waitwhy"), {})
    active_ch = [c for c in channels_out if c["status"] == "active"]
    kpis = [
        dict(label="Suscriptores YouTube", value=net_subs, unit="",
             delta=sum((c["delta7_subs"] or 0) for c in active_ch), icon="users"),
        dict(label="Visualizaciones YouTube", value=net_views, unit="",
             delta=sum((c["delta7_views"] or 0) for c in active_ch), icon="eye"),
        dict(label="Seguidores en redes", value=social_followers, unit="",
             delta=sum((s["delta7"] or 0) for s in socials_out), icon="share"),
        dict(label="Vídeos publicados", value=net_videos, unit="", delta=None, icon="film"),
        dict(label="Éxito IG (14 días)", value=ig.get("rate_recent", ig["rate"]),
             unit="%", delta=None, icon="instagram"),
        dict(label="Canales activos", value=len(active_ch),
             unit=f"/{len(channels_out)}", delta=None, icon="grid"),
    ]

    # ── conclusiones automáticas (todo derivado de datos reales) ──
    insights = []
    if net_views and yt_flagship:
        share = round(100 * yt_flagship["views"] / net_views) if net_views else 0
        insights.append(dict(tone="info", title="WaitWhy es el motor de la red",
            body=f"Concentra el {share}% de las visualizaciones de YouTube "
                 f"({yt_flagship['views']:,} de {net_views:,}) y {yt_flagship['subs']} de "
                 f"{net_subs} subs. El true crime/corrupción ES sigue siendo el nicho ganador."))
    # canal con mejor views/vídeo (excl. flagship)
    eff = [(c, round(c["views"] / c["videos"])) for c in active_ch
           if c["videos"] and not c.get("flagship")]
    if eff:
        eff.sort(key=lambda x: x[1], reverse=True)
        best, vpv = eff[0]
        insights.append(dict(tone="good", title=f"{best['name']}: mejor rendimiento secundario",
            body=f"{vpv:,} visualizaciones por vídeo de media ({best['views']:,} vistas / "
                 f"{best['videos']} vídeos). Categoría: {best['cat']}."))
    if top_topics:
        kws = ", ".join(t["keyword"] for t in top_topics[:5])
        insights.append(dict(tone="good", title="Temas que más funcionan",
            body=f"Por vistas medias destacan: {kws}. Priorizar estos ángulos en próximos guiones."))
    if worst_topics:
        kws = ", ".join(t["keyword"] for t in worst_topics[:5])
        insights.append(dict(tone="warn", title="Temas de bajo rendimiento",
            body=f"Menos tracción: {kws}. Reducir o replantear estos enfoques."))
    if ig["rate"] is not None:
        rr = ig.get("rate_recent")
        base = rr if rr is not None else ig["rate"]
        tone = "good" if base >= 80 else ("warn" if base >= 55 else "bad")
        insights.append(dict(tone=tone, title=f"Instagram: {base}% de éxito (últimos 14 días)",
            body=f"{ig.get('ok_recent', ig['ok'])}/{ig.get('total_recent', ig['total'])} vídeos "
                 f"publicados desde el cambio a Cloudflare R2 + retry. "
                 f"(Histórico global: {ig['rate']}%, incluye la etapa previa catbox/litterbox.)"))
    paused = [c["name"] for c in channels_out if c["status"] == "paused"]
    if paused:
        insights.append(dict(tone="info", title=f"{len(paused)} canales en pausa (consolidación)",
            body="Pausados para priorizar calidad sobre volumen: " + ", ".join(paused) + "."))
    no_track = [c["name"] for c in channels_out
                if c["group"] == "core" and c["status"] == "active" and not c["has_analytics"]]
    if no_track:
        insights.append(dict(tone="info", title="Nuevos canales entrando en analítica",
            body="Empiezan a medirse en el próximo snapshot diario: " + ", ".join(no_track) +
                 " (snapshot YT_IA / YT_AITOOLS recién añadido)."))
    # huecos de producción en los 10 canales core
    core = [c for c in channels_out if c["group"] == "core"]
    miss_long = [c["name"] for c in core if c.get("missing_long")]
    if miss_long:
        insights.append(dict(tone="warn", title="Canales sin long-form programado",
            body="Solo suben Shorts (falta el long-form semanal): " + ", ".join(miss_long) + "."))
    stalled = [c["name"] for c in core
               if c["has_analytics"] and c["health"] in ("inactivo", "sin_subidas")]
    if stalled:
        insights.append(dict(tone="bad", title="Canales sin subidas recientes",
            body="Sin actividad detectada últimamente: " + ", ".join(stalled) +
                 ". Revisar cron / credenciales."))
    ig_ch = [c["name"] for c in channels_out if c.get("ig")]
    if ig_ch:
        insights.append(dict(tone="info", title="Instagram: solo nicho true crime ES",
            body="Para no hundir el alcance por mezclar nichos (Originality Score de Meta), "
                 "solo suben a IG @waitwhy_: " + ", ".join(ig_ch) +
                 ". El resto omite IG a propósito (~3-4 reels/día, sweet spot Meta)."))
    # descubrimiento: cuánto rinde el true crime vs la media de la red
    act_vpv = [c["views"] / c["videos"] for c in channels_out if c["videos"] and c["views"] > 0]
    if act_vpv:
        net_avg = sum(act_vpv) / len(act_vpv)
        tc = next((c for c in channels_out if c["key"] == "waitwhy"), None)
        if tc and tc["videos"] and net_avg:
            mult = round((tc["views"] / tc["videos"]) / net_avg, 1)
            insights.append(dict(tone="good", title=f"El true crime rinde {mult}× la media",
                body=f"WaitWhy hace {round(tc['views'] / tc['videos']):,} views/vídeo frente a "
                     f"{round(net_avg):,} de media de la red. La palanca #1 es la temática."))
    # descubrimiento: ES vs EN
    if len(by_language) >= 2:
        es = next((l for l in by_language if l["lang"] == "ES"), None)
        en = next((l for l in by_language if l["lang"] == "EN"), None)
        if es and en and es["vpv"] and en["vpv"]:
            insights.append(dict(tone="info", title="Español rinde más que inglés (por ahora)",
                body=f"ES: {es['vpv']:,} views/vídeo ({es['channels']} canales) · "
                     f"EN: {en['vpv']:,} ({en['channels']}). Los canales EN son nuevos; a vigilar."))
    # descubrimiento: qué está EN RACHA
    if trending:
        t0 = trending[0]
        insights.append(dict(tone="good", title="En racha ahora mismo",
            body=f"«{t0['title'][:60]}» (+{t0['delta']:,} views en 7 días). "
                 f"Mira la pestaña Contenido para el resto de vídeos que despegan."))

    # ── (2) ALERTAS automáticas: qué necesita atención AHORA ──
    alerts = []
    if trending:
        alerts.append(dict(tone="good", title=f"Despegando: {trending[0]['title'][:46]}",
                           body=f"+{trending[0]['delta']:,} views en 7 días. Considera un vídeo relacionado."))
    for c in channels_out:
        if c["status"] == "active" and c.get("delta7_subs") is not None and c["delta7_subs"] < 0:
            alerts.append(dict(tone="warn", title=f"{c['name']} pierde seguidores",
                               body=f"{c['delta7_subs']} suscriptores en 7 días."))
    for c in channels_out:
        if c["group"] == "core" and c["status"] == "active" and c["has_analytics"] and c["health"] == "inactivo":
            alerts.append(dict(tone="bad", title=f"{c['name']} sin subidas",
                               body=f"Última hace {c['days_since']} días. Revisar cron/credenciales."))
    if ig.get("rate_recent") is not None and ig["rate_recent"] < 55:
        alerts.append(dict(tone="bad", title=f"Instagram al {ig['rate_recent']}% (14 días)",
                           body="Ratio de subida bajo — revisar host R2 / verify."))
    mast = next((s for s in socials_out if s["pk"] == "mastodon"), None)
    if mast and (mast.get("delta7") or 0) < 0:
        alerts.append(dict(tone="warn", title="Mastodon pierde seguidores",
                           body=f"{mast['delta7']} en 7 días — la estrategia de hashtags es reciente."))
    th = next((s for s in socials_out if s["pk"] == "threads"), None)
    if th and th["followers"] == 0:
        alerts.append(dict(tone="warn", title="Threads sin seguidores",
                           body="Publica pero no crece; la API no da palancas de growth."))
    alerts = alerts[:9]

    # ── (3) Recomendador "qué publicar ahora" (temas que rinden + mejor momento) ──
    recommendations = []
    bt_day = best_time.get("best_weekday"); bt_hour = best_time.get("best_hour")
    for c in channels_out:
        if c["status"] != "active" or c["group"] != "core":
            continue
        kws = [t["keyword"] for t in (c.get("topics") or [])[:3]]
        if not kws:
            continue
        recommendations.append(dict(
            channel=c["name"], color=c["color"],
            suggestion="Ángulos que rinden: " + ", ".join(kws),
            why=f"Sus temas con más vistas medias" + (f" · mejor {bt_day} ~{bt_hour}" if bt_day else "")))
    recommendations = recommendations[:9]

    # series agregadas de red (forward-fill) para gráficas limpias
    net_series = _merge_ff([c["series"] for c in channels_out if c["series"]], ("subs", "views"))
    social_series = _merge_ff([s["series"] for s in socials_out if s["series"]], ("subs",))

    # ── VISIÓN EJECUTIVA (escala + proyección + rendimiento por nicho + capacidades) ──
    from datetime import date as _date

    def _d(s):
        try:
            return _date.fromisoformat(s)
        except Exception:
            return None

    yt_videos_total = sum(c["videos"] for c in channels_out)
    social_posts_total = sum(s["posts"] for s in socials_out)
    per_day = sum(1 for r in recurring
                  if r["category"] == "content" and r["days"] == "Cada día" and not r["paused"])
    showcase = dict(
        videos_yt=yt_videos_total, posts_social=social_posts_total,
        content_total=yt_videos_total + social_posts_total,
        views_yt=net_views, audience=net_subs + social_followers,
        days=rng["days"], channels=len(core),
        channels_active=len([c for c in channels_out if c["status"] == "active"]),
        networks=1 + len(socials_out), langs=len({c["lang"] for c in channels_out}),
        per_day=per_day, cost=0,
    )
    velocity = {}
    if len(net_series) >= 2:
        w = net_series[-30:] if len(net_series) >= 30 else net_series
        a, b = w[0], w[-1]
        da, db = _d(a["date"]), _d(b["date"])
        span = (db - da).days if (da and db) else 0
        if span > 0:
            sr = (b["subs"] - a["subs"]) / span
            vr = (b["views"] - a["views"]) / span
            velocity = dict(
                span=span, subs_day=round(sr, 1), views_day=round(vr),
                subs_now=b["subs"], views_now=b["views"],
                subs_30=round(b["subs"] + sr * 30), subs_90=round(b["subs"] + sr * 90),
                views_30=round(b["views"] + vr * 30), views_90=round(b["views"] + vr * 90),
            )
    catmap: dict[str, dict] = {}
    for c in channels_out:
        if c["views"] <= 0:
            continue
        m = catmap.setdefault(c["cat"], {"cat": c["cat"], "channels": 0, "videos": 0, "views": 0})
        m["channels"] += 1
        m["videos"] += c["videos"]
        m["views"] += c["views"]
    by_category = sorted(catmap.values(), key=lambda x: x["views"], reverse=True)
    for m in by_category:
        m["vpv"] = round(m["views"] / m["videos"]) if m["videos"] else 0
    capabilities = [
        "Ideas frescas automáticas (prensa/nichos) + anti-repetición semántica",
        "Guion con IA (Gemini) — solo datos verificables + disclaimer legal",
        "Voz neural (Edge-TTS) en ES/EN + música libre de derechos",
        "Render multi-formato: Shorts, long-form, animación Manim, bar-chart-race, satisfying",
        "Miniatura + hook en pantalla + imágenes reales (Pexels/Pixabay)",
        "Subida y programación automática en YouTube (10 canales)",
        "Cross-post a TikTok, Instagram, Bluesky, Mastodon y Threads",
        "Analítica diaria, este panel en tiempo real y reauth por Telegram",
    ]

    # ── Monetización: qué falta para monetizar en cada app (umbrales reales) ──
    def _prog(cur, tgt):
        return dict(current=cur, target=tgt,
                    pct=min(100, round(100 * cur / tgt)) if tgt else 0,
                    missing=max(0, tgt - cur))
    yt_chs = [dict(name=c["name"], flagship=c.get("flagship", False), **_prog(c["subs"], 1000))
              for c in channels_out if c["group"] == "core"]
    tt = next((s for s in socials_out if s["pk"] == "tiktok"), {})
    igp = next((s for s in socials_out if s["pk"] == "instagram"), {})
    monetization = dict(
        youtube=dict(
            label="YouTube · Programa de Socios (YPP)",
            req="1.000 suscriptores + 4.000 h de visionado (12 meses) o 10 M de views de Shorts (90 días)",
            channels=sorted(yt_chs, key=lambda x: x["pct"], reverse=True),
            note="Aquí medimos los suscriptores (la puerta de entrada). Las horas de visionado y las "
                 "views de Shorts en 90 días aún no se capturan en analítica — se añadirán."),
        tiktok=dict(
            label="TikTok · Creativity Program",
            req="10.000 seguidores + 100.000 views (30 días) + 18 años",
            note="El vídeo rinde bien por vídeo, pero falta base de seguidores; además pide 100k "
                 "views/30d. Ojo: la cuenta está en Sandbox (publicación manual hasta pasar review).",
            **_prog(tt.get("followers", 0), 10000)),
        instagram=dict(
            label="Instagram · monetización",
            req="Cuenta profesional + elegibilidad (bonus/insignias, por invitación; ~10k para enlaces)",
            note="La monetización de IG es por invitación y varía por país; el umbral de seguidores es "
                 "orientativo. La palanca real es crecer la cuenta @waitwhy_.",
            **_prog(igp.get("followers", 0), 10000)),
        otras="Bluesky, Mastodon y Threads no tienen monetización nativa: se rentabilizan llevando "
              "tráfico a YouTube, con afiliados o con propinas.",
    )

    return dict(
        generated_at=datetime.now(timezone.utc).isoformat(),
        generated_local=datetime.now(_MADRID).strftime("%Y-%m-%d %H:%M"),
        range=rng, kpis=kpis, insights=insights,
        totals=dict(yt_subs=net_subs, yt_views=net_views, videos=net_videos,
                    social_followers=social_followers),
        net_series=net_series, social_series=social_series,
        channels=channels_out, socials=socials_out,
        content=dict(top_overall=top_overall, worst_overall=worst_overall,
                     top_topics=top_topics, worst_topics=worst_topics,
                     best_time=best_time, engagement_top=engagement_top, case_study=case_study,
                     trending=trending, by_language=by_language),
        ig=ig, crosspost=cross,
        weekday=global_weekday,
        showcase=showcase, velocity=velocity, by_category=by_category, capabilities=capabilities,
        alerts=alerts, recommendations=recommendations, interaction=interaction, funnel=funnel,
        monetization=monetization,
        schedule=dict(recurring=recurring, upcoming=upcoming, history=history[:400],
                      pub_by_day=pub_by_day),
        pages_base=PAGES_BASE,
    )


def write(dest: Path | None = None) -> Path:
    data = build()
    dest = dest or (DOCS / "dashboard" / "data.json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")),
                     encoding="utf-8")
    return dest


def serve(port: int = 5056, open_browser: bool = True) -> None:
    """Sirve el panel en local (http://127.0.0.1:<port>/). Regenera data.json al
    arrancar. Coste cero, sin depender de GitHub Pages. Ctrl+C para parar."""
    import functools
    import http.server
    import socketserver
    import webbrowser

    import threading
    import time

    write()  # datos frescos
    directory = str((DOCS / "dashboard").resolve())

    # rebuild periódico en segundo plano → si stats_history cambia, el panel se
    # actualiza solo (cada 10 min). El front-end también re-consulta data.json.
    def _loop_rebuild():
        while True:
            time.sleep(600)
            try:
                write()
            except Exception as e:
                print(f"  dashboard rebuild fallo: {e}")
    threading.Thread(target=_loop_rebuild, daemon=True).start()

    class _Handler(http.server.SimpleHTTPRequestHandler):
        def guess_type(self, path):
            t = super().guess_type(path)
            # fuerza UTF-8 en HTML y JSON (evita mojibake: ★ ▲ → í Δ)
            if t in ("text/html", "application/json") or str(path).endswith((".html", ".json")):
                base = "text/html" if str(path).endswith(".html") else "application/json"
                return f"{base}; charset=utf-8"
            return t

        def end_headers(self):
            # sin caché → el navegador siempre lee el data.json más reciente
            self.send_header("Cache-Control", "no-store, max-age=0")
            super().end_headers()

        def log_message(self, *_a):  # silencio (no ensuciar la terminal)
            pass

    handler = functools.partial(_Handler, directory=directory)
    socketserver.TCPServer.allow_reuse_address = True
    url = f"http://127.0.0.1:{port}/"
    with socketserver.TCPServer(("127.0.0.1", port), handler) as httpd:
        print(f"\n  📊 Centro de Mando en LOCAL → {url}")
        print(f"     sirviendo {directory}")
        print("     (Ctrl+C para parar)\n")
        if open_browser:
            try:
                webbrowser.open(url)
            except Exception:
                pass
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n  panel detenido.")


if __name__ == "__main__":
    p = write()
    d = json.loads(p.read_text(encoding="utf-8"))
    print(f"✓ {p}  ({p.stat().st_size/1024:.0f} KB)")
    print(f"  canales={len(d['channels'])} redes={len(d['socials'])} "
          f"agenda_próx={len(d['schedule']['upcoming'])} histórico={len(d['schedule']['history'])}")
