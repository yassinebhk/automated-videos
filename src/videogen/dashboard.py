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

CHANNELS: list[dict] = [
    # key(interno)   display                platform_key      handle                url_yt                                        cat            status   lang
    dict(key="waitwhy",    name="WaitWhy",           pk="youtube",         handle="@waitwhy_ybb",     cat="True crime / corrupción", status="active", lang="ES", flagship=True),
    dict(key="ayudas",     name="AyudaGob",          pk="youtube_ayudas",  handle="@AyudaGob_es",     cat="Ayudas y subvenciones",   status="active", lang="ES"),
    dict(key="motor",      name="Motor60s",          pk="youtube_motor",   handle="@Motor60sES",      cat="Motor / curiosidades",    status="active", lang="ES"),
    dict(key="pov",        name="TiempoAtrás ES",    pk="youtube_pov",      handle="@TiempoAtras_ES",  cat="Historia / POV",          status="active", lang="ES"),
    dict(key="ranking",    name="TopRanking ES",     pk="youtube_ranking",  handle="@TopRanking_ES",   cat="Rankings / datos",        status="active", lang="ES"),
    dict(key="ia",         name="IA Autónomos ES",   pk=None,              handle="@IAAutonomos_es",  cat="IA para autónomos",       status="active", lang="ES"),
    dict(key="aitools",    name="AI Tools Weekly",   pk=None,              handle=None,               cat="AI tools",                status="active", lang="EN"),
    dict(key="padel",      name="Pádel",             pk=None,              handle=None,               cat="Pádel (Manim)",           status="active", lang="ES"),
    dict(key="satisfying", name="Infinite Fractals", pk=None,              handle=None,               cat="Satisfying / hipnótico",  status="active", lang="EN"),
    dict(key="tax",        name="TaxHack ES",        pk="youtube_tax",     handle="@TaxHack_es",      cat="Fiscalidad",              status="paused", lang="ES"),
    dict(key="legal",      name="TusDerechos ES",    pk="youtube_legal",   handle="@TusDerechos_ES",  cat="Derecho laboral",         status="paused", lang="ES"),
    dict(key="ambient",    name="MenteEnCalma",      pk="youtube_ambient", handle=None,               cat="Relax / binaural",        status="paused", lang="ES"),
    dict(key="trabajos",   name="CuriosLaboral ES",  pk=None,              handle="@CuriosLaboral_ES",cat="Curiosidades laborales",  status="paused", lang="ES"),
    dict(key="criminopatia", name="Criminopatía",    pk=None,              handle="@Criminopatia_ES", cat="Criminología",            status="paused", lang="ES"),
    dict(key="rankings_en", name="Global Rankings",  pk=None,              handle=None,               cat="Rankings (EN)",           status="paused", lang="EN"),
]

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
    "ambient-daily":          ("MenteEnCalma · Long",    "MenteEnCalma",     "content"),
    "tax-longform-weekly":    ("TaxHack · Long-form",    "TaxHack ES",       "longform"),
    "legal-longform-weekly":  ("TusDerechos · Long-form", "TusDerechos ES",  "longform"),
    "ayudas-longform-weekly": ("AyudaGob · Long-form",   "AyudaGob",         "longform"),
    "motor-longform-weekly":  ("Motor60s · Long-form",   "Motor60s",         "longform"),
    "ai-tools-longform-weekly": ("AI Tools · Long-form", "AI Tools Weekly",  "longform"),
    "pov-longform":           ("TiempoAtrás · Long-form", "TiempoAtrás ES",  "longform"),
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
                        likes=r.get("likes", 0) or 0, date=r.get("date"),
                        url=_video_url(pk, vid))
            vlist.append(item)
            all_videos_flat.append({**item, "channel": ch["name"], "color": color, "cat": ch["cat"]})
            # análisis de temas (solo canales con tracción real)
            if vv > 0 and title:
                for w in re.findall(r"[a-záéíóúñ0-9]{4,}", title.lower()):
                    if w not in _STOP:
                        kw_stats[w].append(vv)
        vlist.sort(key=lambda x: x["views"], reverse=True)
        top_videos = vlist[:6]
        worst_videos = [v for v in reversed(vlist) if v["views"] >= 0][:6]

        if ch["status"] == "active":
            net_subs += subs
            net_views += views
        net_videos += videos

        channels_out.append(dict(
            key=ch["key"], name=ch["name"], handle=ch.get("handle"),
            url=_yt_url(ch.get("handle")), cat=ch["cat"], status=ch["status"],
            lang=ch["lang"], flagship=ch.get("flagship", False), color=color,
            subs=subs, views=views, videos=videos,
            has_analytics=bool(series),
            delta7_subs=_delta(series, "subs", 7), delta30_subs=_delta(series, "subs", 30),
            delta7_views=_delta(series, "views", 7), delta30_views=_delta(series, "views", 30),
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
        socials_out.append(dict(
            pk=s["pk"], name=s["name"], handle=s.get("handle"), url=s.get("url"),
            color=s["color"], followers=followers, posts=posts, likes=likes,
            delta7=_delta(series, "subs", 7), delta30=_delta(series, "subs", 30),
            series=series,
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

    # ── Instagram: ratio real de subidas ──
    ig = dict(total=0, ok=0, fail=0, rate=None, recent=[], by_day=[])
    igp = OUTPUT / "ig_publish_log.json"
    if igp.exists():
        try:
            log = json.loads(igp.read_text(encoding="utf-8"))
            if isinstance(log, list):
                ok = sum(1 for x in log if x.get("status") == "ok")
                fail = len(log) - ok
                ig["total"] = len(log)
                ig["ok"] = ok
                ig["fail"] = fail
                ig["rate"] = round(100 * ok / len(log)) if log else None
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
        dict(label="Éxito subidas IG", value=ig["rate"], unit="%", delta=None, icon="instagram"),
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
        tone = "good" if ig["rate"] >= 80 else ("warn" if ig["rate"] >= 55 else "bad")
        insights.append(dict(tone=tone, title=f"Instagram: {ig['rate']}% de éxito",
            body=f"{ig['ok']} publicados / {ig['fail']} fallidos de los últimos {ig['total']} intentos. "
                 f"Host actual: Cloudflare R2."))
    paused = [c["name"] for c in channels_out if c["status"] == "paused"]
    if paused:
        insights.append(dict(tone="info", title=f"{len(paused)} canales en pausa (consolidación)",
            body="Pausados para priorizar calidad sobre volumen: " + ", ".join(paused) + "."))
    no_track = [c["name"] for c in channels_out if c["status"] == "active" and not c["has_analytics"]]
    if no_track:
        insights.append(dict(tone="warn", title="Canales activos sin analítica dedicada",
            body="No hay snapshot de métricas para: " + ", ".join(no_track) +
                 ". Añadir su snapshot para medir tracción real."))

    # series agregadas de red (forward-fill) para gráficas limpias
    net_series = _merge_ff([c["series"] for c in channels_out if c["series"]], ("subs", "views"))
    social_series = _merge_ff([s["series"] for s in socials_out if s["series"]], ("subs",))

    return dict(
        generated_at=datetime.now(timezone.utc).isoformat(),
        generated_local=datetime.now(_MADRID).strftime("%Y-%m-%d %H:%M"),
        range=rng, kpis=kpis, insights=insights,
        totals=dict(yt_subs=net_subs, yt_views=net_views, videos=net_videos,
                    social_followers=social_followers),
        net_series=net_series, social_series=social_series,
        channels=channels_out, socials=socials_out,
        content=dict(top_overall=top_overall, worst_overall=worst_overall,
                     top_topics=top_topics, worst_topics=worst_topics),
        ig=ig, crosspost=cross,
        schedule=dict(recurring=recurring, upcoming=upcoming, history=history[:400]),
        pages_base=PAGES_BASE,
    )


def write(dest: Path | None = None) -> Path:
    data = build()
    dest = dest or (DOCS / "dashboard" / "data.json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")),
                     encoding="utf-8")
    return dest


if __name__ == "__main__":
    p = write()
    d = json.loads(p.read_text(encoding="utf-8"))
    print(f"✓ {p}  ({p.stat().st_size/1024:.0f} KB)")
    print(f"  canales={len(d['channels'])} redes={len(d['socials'])} "
          f"agenda_próx={len(d['schedule']['upcoming'])} histórico={len(d['schedule']['history'])}")
