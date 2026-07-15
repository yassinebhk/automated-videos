"""UI web para videogen: prompt → genera → revisa → valida → sube a YouTube.

Lanzar con:  videogen ui   (abre http://localhost:5005)
"""
from __future__ import annotations

import threading
import uuid
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_file

from . import service
from .config import PENDING_DIR, UPLOADED_DIR

app = Flask(__name__)

# Job store en memoria: job_id -> dict(status, log[], slug, error, links)
JOBS: dict[str, dict] = {}


def _run_generate(job_id: str, topic: str, ai_hero: bool = True):
    job = JOBS[job_id]

    def progress(msg: str):
        job["log"].append(msg)

    try:
        job["status"] = "generating"
        slug = service.generate(topic, langs=("es", "en"), progress=progress, ai_hero=ai_hero)
        job["slug"] = slug
        job["meta"] = service.get_meta(slug)
        job["status"] = "ready"
        progress("✅ Listo para revisar")
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)
        progress(f"❌ Error: {e}")


def _run_publish(job_id: str, slug: str, publish_at: str | None = None):
    job = JOBS[job_id]

    def progress(msg: str):
        job["log"].append(msg)

    try:
        job["status"] = "publishing"
        links = service.publish(
            slug, langs=("es", "en"), privacy="public", progress=progress,
            publish_at=publish_at,
        )
        job["links"] = links
        job["status"] = "published"
        progress("🗓 Programado en YouTube" if publish_at else "🚀 Publicado en YouTube")
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)
        progress(f"❌ Error al subir: {e}")


@app.post("/generate")
def generate():
    body = request.json or {}
    topic = body.get("topic", "").strip()
    ai_hero = bool(body.get("ai_hero", True))
    if not topic:
        return jsonify({"error": "prompt vacío"}), 400
    job_id = uuid.uuid4().hex[:8]
    JOBS[job_id] = {"status": "queued", "log": [], "slug": None, "topic": topic}
    threading.Thread(target=_run_generate, args=(job_id, topic, ai_hero), daemon=True).start()
    return jsonify({"job_id": job_id})


@app.post("/publish/<job_id>")
def publish(job_id: str):
    job = JOBS.get(job_id)
    if not job or not job.get("slug"):
        return jsonify({"error": "job no listo"}), 400
    publish_at = (request.json or {}).get("publish_at") or None
    threading.Thread(target=_run_publish, args=(job_id, job["slug"], publish_at), daemon=True).start()
    return jsonify({"ok": True})


@app.post("/publish_slug")
def publish_slug():
    body = request.json or {}
    slug = body.get("slug", "").strip()
    publish_at = body.get("publish_at") or None
    if not slug:
        return jsonify({"error": "slug vacío"}), 400
    job_id = uuid.uuid4().hex[:8]
    JOBS[job_id] = {"status": "queued", "log": [], "slug": slug}
    threading.Thread(target=_run_publish, args=(job_id, slug, publish_at), daemon=True).start()
    return jsonify({"job_id": job_id})


@app.get("/history")
def history():
    return jsonify(service.list_history())


@app.get("/status/<job_id>")
def status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "no existe"}), 404
    return jsonify(job)


@app.get("/video/<slug>/<lang>")
def video(slug: str, lang: str):
    p = service.video_path(slug, lang)
    if not p:
        abort(404)
    return send_file(p, mimetype="video/mp4")


@app.get("/")
def index():
    return INDEX_HTML


@app.get("/docs")
def docs():
    return DOCS_HTML


@app.get("/analytics")
def analytics_page():
    return ANALYTICS_HTML


@app.post("/analytics/snapshot")
def analytics_snapshot():
    from . import analytics as _an
    try:
        counts = _an.snapshot_all()
        charts = _an.render_all()
        return jsonify({"ok": True, "snapshot": counts, "charts": list(charts.keys())})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.get("/chart/<platform>.png")
def chart_png(platform: str):
    from . import analytics as _an
    if platform not in _an.PLATFORMS:
        abort(404)
    path = _an.CHARTS_DIR / f"chart_{platform}.png"
    if not path.exists():
        # render on demand
        _an.render_platform_chart(platform, path)
    if not path.exists():
        abort(404)
    return send_file(path, mimetype="image/png")


# ─────────────────────────── estilos compartidos ───────────────────────────
_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,900&family=Hanken+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@500;700&display=swap');
:root{
  --bg:#f3eee6; --surface:#fbf8f1; --ink:#2a2521; --body:#4a443c; --muted:#8a8074;
  --gold:#c0633f; --gold2:#a84e2c; --green:#ad8636; --line:#e7dece;
  --glass:#fbf8f1; --glassborder:#e8dfd0; --code:#2a2521;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--body);
  font-family:'Hanken Grotesk',sans-serif;line-height:1.65;-webkit-font-smoothing:antialiased;min-height:100vh;
  background-image:
    radial-gradient(72vw 55vh at 92% -20%, rgba(192,99,63,.11), transparent 60%),
    radial-gradient(56vw 48vh at -8% 6%, rgba(173,134,54,.08), transparent 62%);
  background-attachment:fixed}
body::after{content:"";position:fixed;inset:0;z-index:-1;pointer-events:none;opacity:.045;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='2'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")}
::selection{background:rgba(192,99,63,.2);color:var(--ink)}
a{color:var(--gold);text-decoration:none}
.serif{font-family:'Fraunces',serif}
.mono{font-family:'JetBrains Mono',monospace}
.gold-text{background:linear-gradient(96deg,#c0633f,#d98a5f);
  -webkit-background-clip:text;background-clip:text;color:transparent}
.wrap{max-width:1080px;margin:0 auto;padding:0 24px}
nav{position:sticky;top:0;z-index:50;backdrop-filter:blur(16px);
  background:rgba(243,238,230,.78);border-bottom:1px solid var(--line)}
nav .row{display:flex;align-items:center;justify-content:space-between;height:66px}
.brand{display:flex;align-items:center;gap:11px;font-weight:700;letter-spacing:.2px;color:var(--ink)}
.mark{width:36px;height:36px;border-radius:11px;display:grid;place-items:center;font-weight:900;color:#fff;
  background:linear-gradient(140deg,#d07a4e,#a84e2c);box-shadow:0 8px 22px -6px rgba(168,78,44,.45)}
.navlinks a{color:var(--muted);margin-left:24px;font-size:14.5px;font-weight:600;transition:.2s}
.navlinks a:hover{color:var(--ink)}
.navlinks a.active{color:var(--gold)}
.btn{font-family:inherit;font-size:15px;font-weight:700;border:0;border-radius:13px;padding:14px 28px;cursor:pointer;
  color:#fff;background:linear-gradient(135deg,#cf6e44,#b0492a);transition:.2s;
  box-shadow:0 12px 28px -10px rgba(168,78,44,.5)}
.btn:hover{transform:translateY(-2px);box-shadow:0 18px 36px -12px rgba(168,78,44,.6)}
.btn:disabled{opacity:.45;cursor:not-allowed;transform:none;box-shadow:none}
.btn.ghost{background:transparent;color:var(--gold);border:1px solid var(--glassborder);box-shadow:none}
.btn.ghost:hover{background:rgba(192,99,63,.07)}
.card{background:var(--surface);border:1px solid var(--glassborder);border-radius:22px;padding:28px;
  box-shadow:0 1px 2px rgba(80,50,30,.04), 0 20px 50px -34px rgba(80,50,30,.2)}
.fade{opacity:0;transform:translateY(14px);animation:fade .7s cubic-bezier(.2,.7,.2,1) forwards}
@keyframes fade{to{opacity:1;transform:none}}
.spin{display:inline-block;width:15px;height:15px;border:2px solid rgba(192,99,63,.25);border-top-color:var(--gold);
  border-radius:50%;animation:s 1s linear infinite;vertical-align:-2px}
@keyframes s{to{transform:rotate(360deg)}}
::-webkit-scrollbar{width:10px;height:10px}::-webkit-scrollbar-thumb{background:#d8cdba;border-radius:6px}
::-webkit-scrollbar-track{background:transparent}
"""


# ───────────────────────────── STUDIO (index) ──────────────────────────────
INDEX_HTML = f"""<!doctype html><html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>videogen · studio</title><style>{_CSS}
.hero{{padding:64px 0 38px}}
.eyebrow{{font-family:'JetBrains Mono',monospace;font-size:12px;letter-spacing:3px;text-transform:uppercase;color:var(--gold);margin-bottom:18px}}
.hero h1{{font-family:'Fraunces',serif;font-weight:900;font-size:clamp(38px,6.4vw,76px);line-height:.98;letter-spacing:-1.5px;margin:0;color:var(--ink)}}
.hero p{{color:var(--muted);font-size:18px;max-width:560px;margin:18px 0 0}}
.composer textarea{{width:100%;min-height:120px;resize:vertical;background:rgba(255,255,255,.6);color:var(--ink);
  border:1px solid var(--glassborder);border-radius:16px;backdrop-filter:blur(8px);padding:18px;font:inherit;font-size:16px;transition:.2s}}
.composer textarea:focus{{outline:0;border-color:var(--gold);box-shadow:0 0 0 4px rgba(192,99,63,.13)}}
.composer .lbl{{font-family:'JetBrains Mono',monospace;font-size:12px;letter-spacing:2px;text-transform:uppercase;color:var(--muted);margin-bottom:12px}}
.row{{display:flex;gap:14px;align-items:center;flex-wrap:wrap}}
.term{{font-family:'JetBrains Mono',monospace;font-size:13px;color:#c9b89f;background:#2a2521;border-radius:14px;
  padding:18px;max-height:240px;overflow:auto;white-space:pre-wrap;border:1px solid #3a322b}}
.term .ln{{padding:1px 0}}
.videos{{display:grid;grid-template-columns:1fr 1fr;gap:22px;margin-top:18px}}
@media(max-width:640px){{.videos{{grid-template-columns:1fr}}}}
.phone{{position:relative}}
.phone h3{{font-family:'JetBrains Mono',monospace;font-size:12px;letter-spacing:2px;color:var(--muted);margin:0 0 10px;text-transform:uppercase}}
.phone video{{width:100%;aspect-ratio:9/16;border-radius:18px;background:#000;border:1px solid var(--glassborder);
  box-shadow:0 40px 70px -40px rgba(0,0,0,.9)}}
.pill{{font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:1px;padding:4px 12px;border-radius:99px;
  border:1px solid var(--line);color:var(--gold);text-transform:uppercase}}
.links a{{display:block;color:var(--green);margin:7px 0;font-family:'JetBrains Mono',monospace;font-size:14px}}
.hsec{{margin-top:18px}}
.hrow{{display:flex;align-items:center;gap:16px;padding:15px 16px;border-radius:14px;border:1px solid transparent;
  cursor:pointer;transition:.18s;border-bottom:1px solid rgba(255,255,255,.05)}}
.hrow:hover{{background:rgba(192,99,63,.05);border-color:var(--line)}}
.hrow .t{{flex:1;min-width:0}}
.hrow .t b{{display:block;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:15px}}
.hrow .t small{{color:var(--muted);font-family:'JetBrains Mono',monospace;font-size:12px}}
.dot{{font-family:'JetBrains Mono',monospace;font-size:11px;padding:3px 11px;border-radius:99px;white-space:nowrap}}
.dot.up{{background:rgba(173,134,54,.14);color:var(--green)}}
.dot.pe{{background:rgba(192,99,63,.12);color:var(--gold)}}
.foot{{color:var(--muted);font-size:13px;text-align:center;padding:50px 0 30px;font-family:'JetBrains Mono',monospace}}
</style></head><body>
<nav><div class="wrap row"><div class="brand"><span class="mark">$</span> videogen</div>
  <div class="navlinks"><a href="/" class="active">Studio</a><a href="/analytics">Analytics</a><a href="/docs">Documentación</a></div></div></nav>

<div class="wrap">
  <header class="hero fade">
    <div class="eyebrow">Estudio de vídeos · nicho dinero</div>
    <h1>Una idea.<br><span class="gold-text">Un vídeo que paga.</span></h1>
    <p>Escribe una curiosidad de dinero. La convertimos en un Short bilingüe — guion, voz, imágenes y datos — listo para YouTube y redes.</p>
  </header>

  <section class="card composer fade" style="animation-delay:.06s">
    <div class="lbl">◢ Tu idea</div>
    <textarea id="topic" placeholder="Ej: Cuánto gana Cristiano Ronaldo por segundo · Por qué los ricos no usan su dinero · El coste real de fabricar un iPhone"></textarea>
    <div class="row" style="margin-top:16px">
      <button class="btn" id="genBtn" onclick="generate()">Generar vídeo →</button>
      <span id="genState" style="color:var(--muted);font-family:'JetBrains Mono',monospace;font-size:13px"></span>
    </div>
    <label title="Genera un frame fotorrealista IA para el arranque (gratis, vía Pollinations). En temas de un famoso se usa su foto real." style="display:inline-flex;align-items:center;gap:9px;margin-top:16px;color:var(--muted);font-family:'JetBrains Mono',monospace;font-size:13px;cursor:pointer">
      <input type="checkbox" id="aiHero" checked style="width:16px;height:16px;accent-color:var(--gold)">
      🎨 Imagen IA en el teaser <span style="opacity:.7">· Pollinations, gratis</span>
    </label>
  </section>

  <section class="card fade" id="logCard" style="display:none;margin-top:22px"><div class="term" id="log"></div></section>

  <section class="card fade" id="reviewCard" style="display:none;margin-top:22px">
    <div class="row" style="justify-content:space-between">
      <strong class="serif" id="reviewTitle" style="font-size:22px"></strong>
      <span class="pill" id="status"></span>
    </div>
    <div class="videos">
      <div class="phone"><h3>🇪🇸 Español</h3><video id="vidEs" controls playsinline></video></div>
      <div class="phone"><h3>🇬🇧 English</h3><video id="vidEn" controls playsinline></video></div>
    </div>
    <div class="row" style="margin-top:22px">
      <button class="btn" id="pubBtn" onclick="publish()">✓ Validar y subir a YouTube</button>
      <button class="btn ghost" onclick="reset()">Descartar</button>
    </div>
    <div class="row" style="margin-top:14px;gap:10px;align-items:center;flex-wrap:wrap">
      <span style="font-family:'JetBrains Mono',monospace;font-size:12px;letter-spacing:1px;text-transform:uppercase;color:var(--muted)">🗓 o programa para</span>
      <input type="datetime-local" id="schedAt" style="background:rgba(255,255,255,.6);color:var(--ink);border:1px solid var(--glassborder);border-radius:11px;padding:9px 12px;font:inherit;font-size:14px">
      <button class="btn ghost" id="schBtn" onclick="schedule()">Programar</button>
    </div>
    <div class="links" id="links" style="margin-top:14px"></div>
  </section>

  <section class="card hsec fade" style="margin-top:22px;animation-delay:.12s">
    <div class="row" style="justify-content:space-between;margin-bottom:8px">
      <strong class="serif" style="font-size:20px">Historial</strong>
      <button class="btn ghost" style="padding:8px 16px;font-size:13px" onclick="loadHistory()">↻ Refrescar</button>
    </div>
    <div id="history"><span style="color:var(--muted)">Cargando…</span></div>
  </section>
  <div class="foot">videogen · pipeline 100% gratis · <a href="/docs">cómo funciona →</a></div>
</div>
<script>
let job=null, timer=null;
const $=id=>document.getElementById(id);
async function generate(){{
  const topic=$('topic').value.trim(); if(!topic)return;
  const aiHero=$('aiHero')?$('aiHero').checked:true;
  $('genBtn').disabled=true; $('genState').innerHTML='<span class="spin"></span> generando…';
  $('logCard').style.display='block'; $('reviewCard').style.display='none'; $('links').innerHTML='';
  const r=await fetch('/generate',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{topic,ai_hero:aiHero}})}});
  const j=await r.json(); job=j.job_id; timer=setInterval(poll,1500);
}}
async function poll(){{
  if(!job)return; const s=await(await fetch('/status/'+job)).json();
  $('log').innerHTML=(s.log||[]).map(l=>'<div class="ln">'+l.replace(/</g,'&lt;')+'</div>').join('');
  $('log').scrollTop=1e9; $('status').textContent=s.status||'';
  if(s.status==='ready'){{clearInterval(timer);$('genState').textContent='';$('genBtn').disabled=false;showReview(s);loadHistory();}}
  else if(s.status==='published'){{clearInterval(timer);showLinks(s.links);$('pubBtn').disabled=false;$('pubBtn').textContent='✓ Publicado';loadHistory();}}
  else if(s.status==='error'){{clearInterval(timer);$('genState').textContent='error';$('genBtn').disabled=false;if($('pubBtn'))$('pubBtn').disabled=false;}}
}}
function showReview(s){{
  $('reviewCard').style.display='block';
  $('reviewTitle').textContent=(s.meta&&s.meta.es?s.meta.es.title:'')||'Revisa los vídeos';
  $('vidEs').src='/video/'+s.slug+'/es?'+Date.now(); $('vidEn').src='/video/'+s.slug+'/en?'+Date.now();
}}
function showLinks(links){{const el=$('links');el.innerHTML='';for(const k in(links||{{}})){{const a=document.createElement('a');a.href=links[k];a.target='_blank';a.textContent='↗ '+k.toUpperCase()+': '+links[k];el.appendChild(a);}}}}
async function doPublish(publishAt){{
  if(!job)return; $('pubBtn').disabled=true; if($('schBtn'))$('schBtn').disabled=true;
  $('pubBtn').innerHTML='<span class="spin"></span> '+(publishAt?'programando…':'subiendo…');
  const payload=publishAt?{{publish_at:publishAt}}:{{}};
  const r=await fetch('/publish/'+job,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(payload)}});
  if(r.status>=400){{const j=await(await fetch('/publish_slug',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(Object.assign({{slug:job}},payload))}})).json();job=j.job_id;}}
  $('logCard').style.display='block'; timer=setInterval(poll,1500);
}}
async function publish(){{ return doPublish(null); }}
async function schedule(){{
  const v=$('schedAt').value; if(!v){{alert('Elige fecha y hora primero');return;}}
  if(new Date(v)<=new Date()){{alert('Esa hora ya pasó — elige una futura');return;}}
  return doPublish(new Date(v).toISOString());
}}
function reset(){{job=null;if(timer)clearInterval(timer);$('topic').value='';$('reviewCard').style.display='none';$('logCard').style.display='none';$('pubBtn').disabled=false;$('pubBtn').textContent='✓ Validar y subir a YouTube';}}
async function loadHistory(){{
  const items=await(await fetch('/history')).json(); const el=$('history');
  if(!items.length){{el.innerHTML='<span style="color:var(--muted)">Aún no hay vídeos. Genera el primero arriba.</span>';return;}}
  el.innerHTML='';
  for(const it of items){{
    const d=document.createElement('div'); d.className='hrow';
    const dot=it.status==='uploaded'?'<span class="dot up">Subido</span>':'<span class="dot pe">Pendiente</span>';
    const links=Object.entries(it.youtube||{{}}).map(([k,v])=>`<a href="${{v}}" target="_blank" onclick="event.stopPropagation()" style="margin-right:9px">${{k.toUpperCase()}}↗</a>`).join('');
    d.innerHTML=`<div class="t"><b>${{it.title_es||it.topic}}</b><small>${{(it.langs||[]).join(' · ')||'—'}} ${{links}}</small></div>${{dot}}`;
    d.onclick=()=>openHistory(it); el.appendChild(d);
  }}
}}
function openHistory(it){{
  job=it.slug; $('reviewCard').style.display='block';
  $('reviewTitle').textContent=it.title_es||it.topic; $('status').textContent=it.status;
  $('vidEs').src='/video/'+it.slug+'/es?'+Date.now(); $('vidEn').src='/video/'+it.slug+'/en?'+Date.now();
  showLinks(it.youtube||{{}});
  const pub=$('pubBtn');
  if(it.status==='uploaded'){{pub.disabled=true;pub.textContent='✓ Ya subido';}}else{{pub.disabled=false;pub.textContent='✓ Validar y subir a YouTube';}}
  window.scrollTo({{top:$('reviewCard').offsetTop-30,behavior:'smooth'}});
}}
loadHistory();
</script></body></html>"""


# ───────────────────────────────── DOCS ────────────────────────────────────
DOCS_HTML = f"""<!doctype html><html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>videogen · documentación</title><style>{_CSS}
.layout{{display:grid;grid-template-columns:240px 1fr;gap:48px;align-items:start;padding:48px 0 90px}}
@media(max-width:860px){{.layout{{grid-template-columns:1fr;gap:24px}}.toc{{position:static!important}}}}
.toc{{position:sticky;top:90px}}
.toc .lbl{{font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:2px;text-transform:uppercase;color:var(--gold);margin-bottom:14px}}
.toc a{{display:block;color:var(--muted);font-size:14px;padding:6px 0;border-left:2px solid transparent;padding-left:14px;transition:.18s;margin-left:-2px}}
.toc a:hover{{color:var(--ink);border-color:var(--line)}}
.doc h1{{font-family:'Fraunces',serif;font-weight:900;font-size:clamp(34px,5vw,56px);line-height:1;letter-spacing:-1px;margin:0 0 10px;color:var(--ink)}}
.doc .lead{{color:var(--muted);font-size:18px;max-width:620px;margin:0 0 12px}}
.doc h2{{font-family:'Fraunces',serif;font-weight:600;font-size:28px;margin:46px 0 4px;letter-spacing:-.5px;color:var(--ink)}}
.doc h2 .num{{font-family:'JetBrains Mono',monospace;font-size:13px;color:#fff;margin-right:14px;vertical-align:3px;padding:3px 10px;border-radius:8px;background:linear-gradient(135deg,#cf6e44,#a84e2c)}}
.doc h3{{font-size:16px;font-weight:700;color:var(--gold);margin:24px 0 6px}}
.doc p,.doc li{{color:var(--body)}}
.doc .card{{margin:14px 0}}
.doc code{{font-family:'JetBrains Mono',monospace;background:#f0e6d6;padding:2px 7px;border-radius:6px;font-size:13px;color:var(--gold)}}
.doc pre{{font-family:'JetBrains Mono',monospace;background:#322c26;border:1px solid #3a322b;padding:16px;border-radius:13px;overflow:auto;font-size:13px;color:#e6ddcf}}
table{{width:100%;border-collapse:collapse;margin:8px 0;font-size:14px}}
th,td{{text-align:left;padding:10px 12px;border-bottom:1px solid rgba(255,255,255,.06);vertical-align:top}}
th{{color:var(--muted);font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:1px;text-transform:uppercase}}
.tag{{display:inline-block;font-family:'JetBrains Mono',monospace;font-size:11px;padding:2px 9px;border-radius:99px;background:rgba(173,134,54,.14);color:var(--green)}}
.tag.paid{{background:rgba(192,99,63,.13);color:var(--gold)}}
.tag.warn{{background:rgba(248,113,113,.14);color:#f87171}}
.flow{{font-family:'JetBrains Mono',monospace;font-size:12.5px;color:#cdbfa9;background:#322c26;border:1px solid #3a322b;padding:18px;border-radius:14px;white-space:pre;overflow:auto;line-height:1.7}}
.step{{display:flex;gap:16px;margin:14px 0}}
.step .n{{flex:none;width:34px;height:34px;border-radius:10px;display:grid;place-items:center;font-family:'JetBrains Mono',monospace;font-weight:700;
  background:linear-gradient(140deg,#cf6e44,#a84e2c);color:#fff}}
.step .b{{flex:1}} .step .b b{{color:var(--ink)}}
.kbd{{font-family:'JetBrains Mono',monospace;background:#11201a;color:var(--ink);border:1px solid var(--line);border-bottom-width:2px;border-radius:6px;padding:1px 7px;font-size:12px}}
.callout{{border-left:3px solid var(--gold);padding:12px 16px;background:rgba(192,99,63,.06);border-radius:0 10px 10px 0;margin:14px 0}}
.callout.warn{{border-color:#f87171;background:rgba(248,113,113,.05)}}
</style></head><body>
<nav><div class="wrap row"><div class="brand"><span class="mark">$</span> videogen</div>
  <div class="navlinks"><a href="/">Studio</a><a href="/analytics">Analytics</a><a href="/docs" class="active">Documentación</a></div></div></nav>
<div class="wrap layout">
  <aside class="toc fade">
    <div class="lbl">◢ Visión general</div>
    <a href="#que">01 · Qué es</a>
    <a href="#nicho">02 · El nicho: dinero</a>
    <a href="#filosofia">03 · Filosofía: gratis</a>
    <div class="lbl" style="margin-top:22px">◢ Cómo se crea</div>
    <a href="#pipeline">04 · El pipeline (visión)</a>
    <a href="#guion">05 · El guion (Gemini)</a>
    <a href="#voz">06 · La voz (Edge TTS)</a>
    <a href="#visuales">07 · Los visuales</a>
    <a href="#overlays">08 · Overlays de datos</a>
    <a href="#montaje">09 · El montaje (ffmpeg)</a>
    <div class="lbl" style="margin-top:22px">◢ Operación</div>
    <a href="#telegram">10 · Telegram</a>
    <a href="#subida">11 · Subida automática</a>
    <a href="#crosspost">12 · Cross-posting</a>
    <a href="#comandos">13 · Comandos del bot</a>
    <a href="#siempre">14 · Que funcione siempre</a>
    <a href="#deploy">15 · Despliegue 24/7</a>
    <div class="lbl" style="margin-top:22px">◢ Referencia</div>
    <a href="#archivos">16 · Estructura de archivos</a>
    <a href="#config">17 · Configuración (.env)</a>
    <a href="#recursos">18 · Recursos y costes</a>
    <a href="#ejemplo">19 · Ejemplo completo</a>
    <a href="#limites">20 · Limitaciones</a>
    <a href="#faq">21 · FAQ</a>
    <a href="#glosario">22 · Glosario</a>
  </aside>
  <main class="doc fade" style="animation-delay:.06s">
    <div class="eyebrow" style="font-family:'JetBrains Mono',monospace;font-size:12px;letter-spacing:3px;text-transform:uppercase;color:var(--gold);margin-bottom:14px">Documentación técnica · v1</div>
    <h1>Cómo funciona <span class="gold-text">videogen</span></h1>
    <p class="lead">La guía completa: qué es, cómo convierte una frase en un vídeo publicado, qué hace cada pieza por dentro, cómo operarlo desde el móvil y toda la referencia técnica. De lo general a lo concreto.</p>

    <!-- ══════════════ PARTE A · VISIÓN GENERAL ══════════════ -->

    <h2 id="que"><span class="num">01</span>Qué es</h2>
    <div class="card">
      <p><b>videogen</b> es un sistema que convierte una <b>idea escrita en una frase</b> en un <b>vídeo corto vertical</b> (formato 9:16, para YouTube Shorts, TikTok y Reels), <b>bilingüe</b> (español + inglés), y lo <b>publica en YouTube automáticamente</b>. Tú solo das el tema; el resto ocurre solo en ~2-3 minutos.</p>
      <p>Lo manejas de dos formas, las dos equivalentes:</p>
      <ul>
        <li><b>Bot de Telegram</b> — escribes la idea desde el móvil, recibes los vídeos y los validas con un botón. Es el modo del día a día.</li>
        <li><b>UI web</b> (esta página/Studio) — misma lógica con interfaz visual, historial y previews. Útil desde el ordenador.</li>
      </ul>
      <div class="callout"><b>Concepto clave:</b> el vídeo NO se "genera" con una IA de vídeo (eso cuesta mucho dinero y aún se ve artificial). Se <b>ENSAMBLA</b>: se juntan piezas reales (clips de stock, fotos con licencia, música libre) con voz sintética y texto generado. La IA generativa interviene solo en dos sitios: el <b>guion</b> (Gemini) y la <b>voz</b> (Edge TTS).</div>
      <h3>Qué NO es</h3>
      <ul>
        <li>No es un generador de vídeo por IA tipo Sora/Veo (de pago, y aquí no hace falta).</li>
        <li>No inventa datos verificados por ti: Gemini redacta, pero conviene revisar cifras sensibles.</li>
        <li>No publica en TikTok/Instagram solo del todo: esas redes no dan API gratis (ver <a href="#crosspost">§12</a>).</li>
      </ul>
    </div>

    <h2 id="nicho"><span class="num">02</span>El nicho: curiosidades de dinero</h2>
    <div class="card">
      <p>El canal está enfocado en <b>curiosidades de dinero</b> 💰 (cuánto gana X, cuánto cuesta Y, fortunas, fraudes históricos, economía curiosa). Es una elección estratégica, no estética:</p>
      <table>
        <tr><th>Razón</th><th>Detalle</th></tr>
        <tr><td>CPM alto</td><td>Finanzas/dinero es de los nichos que <b>más paga</b> por mil reproducciones (anunciantes premium).</td></tr>
        <tr><td>Enganche universal</td><td>"Cuánto gana…" activa curiosidad inmediata en cualquier idioma.</td></tr>
        <tr><td>Visualizable</td><td>Se presta a <b>números grandes</b> en pantalla (overlays), que retienen la atención.</td></tr>
        <tr><td>Material disponible</td><td>Hay stock (billetes, ciudades, coches) y fotos CC de los famosos implicados.</td></tr>
      </table>
      <p>La identidad del nicho (tono, tipos de tema, qué keywords visuales usar, qué evitar) vive en <code>prompts/niche.md</code> y se inyecta en cada guion. Por eso todos los vídeos "suenan" coherentes.</p>
      <div class="callout">Validación real observada: vídeos como el del pulpo (1.107 views ES) o "Grupo de la Muerte" (1.078 views ES) confirman que el formato + nicho conectan.</div>
    </div>

    <h2 id="filosofia"><span class="num">03</span>Filosofía: lo más gratis posible</h2>
    <div class="card">
      <p>Toda decisión de diseño prioriza el <b>coste cero</b>. Cada vez que hay una opción de pago y una gratuita aceptable, se elige la gratuita:</p>
      <ul>
        <li>Guion → <b>Gemini free tier</b> (no OpenAI de pago).</li>
        <li>Voz → <b>Edge TTS</b> de Microsoft, ilimitada y gratis (no ElevenLabs salvo que se active aposta).</li>
        <li>Imágenes/clips → <b>Pexels + Wikimedia Commons</b> (no generación IA de pago).</li>
        <li>Música → <b>Incompetech</b> (CC-BY, atribución en descripción).</li>
        <li>Montaje → <b>ffmpeg local</b> (no servicios de render en nube).</li>
        <li>Hosting 24/7 → <b>Oracle Cloud Free Tier</b> (gratis para siempre).</li>
      </ul>
      <p>El segundo principio es <b>operación desde el móvil</b>: lo que pueda hacerse por Telegram, se hace por Telegram. Lo que no tiene API gratis (subir a TikTok) se reduce a "dos toques".</p>
    </div>

    <!-- ══════════════ PARTE B · CÓMO SE CREA ══════════════ -->

    <h2 id="pipeline"><span class="num">04</span>El pipeline en 6 etapas</h2>
    <div class="card">
      <p>Un prompt no lo resuelve una sola IA: atraviesa una <b>cadena de 6 etapas</b>, cada una con una herramienta especializada. Las secciones 05–09 explican cada etapa a fondo.</p>
      <div class="flow">prompt  "Cuánto gana CR7 por segundo"
  │
  ├─ 1. GUION ······ Gemini → teaser · hook · body · CTA · music_mood
  │                          · visual_keywords · subject_person · hashtags
  ├─ 2. VOZ ········ Edge TTS narra ES y EN (audio + timestamp por palabra)
  ├─ 3. VISUALES ··· Pexels (clips de stock) + Wikimedia (foto del famoso, CC)
  ├─ 4. OVERLAYS ··· Pillow dibuja los datos grandes  ("6€ / POR SEGUNDO")
  ├─ 5. MONTAJE ···· ffmpeg une clips + voz + música + overlays + subtítulos
  └─ 6. SUBIDA ····· YouTube Data API publica el MP4 + variante TikTok sin subs
  │
  ▼  vídeo en YouTube  +  notificación a Telegram</div>
      <p>Todo se ejecuta en tu máquina (excepto las llamadas a APIs). El resultado por idioma: <code>video_es_vertical.mp4</code> (con música+subtítulos, para YouTube) y <code>video_es_vertical_tiktok.mp4</code> (sin música, para añadir audio trending).</p>
    </div>

    <h2 id="guion"><span class="num">05</span>Etapa 1 · El guion (Gemini)</h2>
    <div class="card">
      <p>El cerebro del vídeo. Gemini recibe tu idea + el <i>system prompt</i> (combinación de <code>prompts/niche.md</code> y <code>prompts/script_system.md</code>) y devuelve un <b>JSON estructurado</b> bilingüe. No es solo "texto": Gemini toma decisiones creativas.</p>
      <h3>Anatomía del guion</h3>
      <table>
        <tr><th>Campo</th><th>Qué es</th></tr>
        <tr><td><code>teaser</code></td><td>Los primeros ~5s. Frases <b>conectadas y fluidas</b> (no entrecortadas) que enganchan antes de revelar nada.</td></tr>
        <tr><td><code>hook</code></td><td>La pregunta/afirmación que plantea la curiosidad central.</td></tr>
        <tr><td><code>body</code></td><td>El desarrollo: los datos curiosos, uno tras otro.</td></tr>
        <tr><td><code>cta</code></td><td>Llamada a la acción final (sigue, comenta…).</td></tr>
        <tr><td><code>visual_keywords</code></td><td>Palabras en inglés por segmento para buscar clips en Pexels. Cuidan coherencia de época y contexto; nunca usan el nombre del famoso como keyword (se usa su foto real).</td></tr>
        <tr><td><code>music_mood</code></td><td>Uno de 10 ánimos musicales (ver <a href="#montaje">§09</a>).</td></tr>
        <tr><td><code>subject_person</code></td><td>Si el tema gira sobre una persona pública, su nombre → dispara la búsqueda de fotos CC.</td></tr>
        <tr><td><code>title · description · hashtags</code></td><td>Metadatos SEO para YouTube, por idioma.</td></tr>
      </table>
      <h3>Robustez</h3>
      <ul>
        <li><b>Cadena de modelos de respaldo:</b> <code>gemini-2.5-flash → flash-lite → flash-latest</code>. Si uno da error 429/503, prueba el siguiente.</li>
        <li><b>Reintento de JSON:</b> si la respuesta llega truncada, reintenta (límite subido a 16.384 tokens).</li>
        <li><b>Escrito "para el oído":</b> el prompt pide texto con pocas comas para que la voz fluya sin pausas raras.</li>
      </ul>
    </div>

    <h2 id="voz"><span class="num">06</span>Etapa 2 · La voz (Edge TTS)</h2>
    <div class="card">
      <p>La narración usa <b>Edge TTS</b> de Microsoft: voces neuronales de calidad, <b>gratis e ilimitadas</b>. Voz por defecto en ES: <code>es-ES-AlvaroNeural</code> a <b>+10% de velocidad</b> (más ágil, menos "lento").</p>
      <h3>Lo que importa de verdad</h3>
      <ul>
        <li><b>Timestamps por palabra</b> (<code>WordBoundary</code>): Edge devuelve cuándo se pronuncia cada palabra. Esto permite generar <b>subtítulos sincronizados</b> y alinear los overlays con lo que se dice.</li>
        <li><b>Limpieza para TTS</b> (<code>_clean_for_tts</code>): se quitan las comas de respiración que cortan el ritmo, <b>conservando</b> las de los decimales (6,5 millones no se rompe). Resultado: locución fluida, sin pausas artificiales — el problema que más se pulió.</li>
      </ul>
      <div class="callout"><b>Voz premium opcional:</b> ElevenLabs (más humana) se activa con <code>VOICE_ENGINE=elevenlabs</code> en <code>.env</code> <span class="tag paid">~$5/mes</span>. Por defecto está en Edge, gratis.</div>
    </div>

    <h2 id="visuales"><span class="num">07</span>Etapa 3 · Los visuales</h2>
    <div class="card">
      <p>El fondo del vídeo combina <b>dos fuentes</b>:</p>
      <h3>A · Clips de stock (Pexels)</h3>
      <p>Por cada segmento, las <code>visual_keywords</code> de Gemini se buscan en Pexels. No se coge el primer resultado: hay un <b>sistema de puntuación</b> para evitar el clip aleatorio fuera de tema:</p>
      <ul>
        <li><b>+ relevancia:</b> match de las palabras clave en la URL/autor del clip.</li>
        <li><b>− tokens negativos:</b> penaliza fuerte material que rompe el tono (turista, escalador, comida cocinada, dibujos, lifestyle, oficina…).</li>
        <li><b>+ calidad técnica:</b> prioriza resolución cercana a 1080×1920, duración suficiente y orientación vertical correcta.</li>
        <li><b>Anchor del topic:</b> la primera imagen se ancla al sujeto del tema (extraído del slug) para que el arranque sea siempre on-topic.</li>
      </ul>
      <h3>B · Caras de famosos (Wikimedia Commons)</h3>
      <p>Si el guion trae <code>subject_person</code>, se bajan hasta <b>3 fotos reales</b> del personaje desde Wikimedia, <b>filtrando solo licencias CC/Dominio Público</b>. La foto principal abre el teaser y el resto se reparte por el body. La <b>atribución</b> requerida se añade automáticamente a la descripción del vídeo.</p>
      <h3>C · Frame IA del teaser (opcional, gratis)</h3>
      <p>Cuando el tema <b>no</b> es de una persona, se puede generar un <b>frame fotorrealista con IA</b> para el arranque (más impactante que el stock). Se usa <b>Pollinations (Flux)</b>: gratis, sin clave y sin límite práctico. Gemini aporta las keywords, Pollinations genera la imagen 9:16 y se anima con un zoom suave (Ken Burns) como primer clip del teaser.</p>
      <ul>
        <li>Activado por defecto en bot y web (checkbox <span class="kbd">🎨 Imagen IA en el teaser</span>).</li>
        <li>En el bot, para desactivarlo en un vídeo concreto: empieza el mensaje con <code>noia</code>.</li>
        <li>Si hay famoso, se prioriza su <b>foto real</b> y se omite el frame IA (Flux no clava rostros reales).</li>
      </ul>
      <div class="callout warn"><b>Nano Banana 2 (Gemini) no es gratis:</b> su free tier de imágenes es 0 (exige facturación, ~$0.067/img). Por eso el frame IA usa Pollinations, que sí es gratis de verdad.</div>
      <div class="callout">Los clips se cachean por keyword; si una carpeta se mueve (pending → uploaded), las rutas se reescriben solas para no romperse.</div>
    </div>

    <h2 id="overlays"><span class="num">08</span>Etapa 4 · Overlays de datos (Pillow)</h2>
    <div class="card">
      <p>Lo que hace que un vídeo de dinero retenga: los <b>números grandes</b> en pantalla. Con <b>Pillow</b> (local, sin coste) se dibujan tarjetas tipo "<b>6€</b> / POR SEGUNDO" o "<b>1.000 M€</b> / FORTUNA".</p>
      <ul>
        <li>Gemini propone los datos a destacar (<code>graphic_specs</code>), que se guardan en <code>graphic_specs_&lt;lang&gt;.json</code>.</li>
        <li>Cada overlay es un PNG transparente con su tema visual, que ffmpeg superpone en el segmento correspondiente (sincronizado con la voz).</li>
      </ul>
      <p>Existe además un <b>modo Graphics</b> completo (infografías en lugar de footage) para temas sin buen material de stock.</p>
    </div>

    <h2 id="montaje"><span class="num">09</span>Etapa 5 · El montaje (ffmpeg)</h2>
    <div class="card">
      <p><b>ffmpeg</b> (con <code>libass</code> para subtítulos) ensambla todo en un MP4 vertical 1080×1920:</p>
      <div class="flow">clips de fondo  ┐
voz narrada     ┤
música (mood)   ┼──▶ ffmpeg ──▶ video_es_vertical.mp4  (YouTube)
overlays PNG    ┤              └▶ video_es_vertical_tiktok.mp4  (sin música)
subtítulos ASS  ┘                 └▶ share_es.mp4  (~12 MB, para enviar/cross-post)</div>
      <h3>Subtítulos</h3>
      <p>Se generan en formato <b>ASS</b> a partir de los timestamps de Edge: fuente Montserrat, en <b>trozos de ~2 palabras</b> (estilo dinámico tipo TikTok), quemados en la versión de YouTube.</p>
      <h3>Texto-hook (segundo 0)</h3>
      <p>Todos los vídeos llevan un <b>texto-gancho grande</b> sobre el primer ~2,4s (frase del <code>thumbnail_text</code>, en mayúsculas con borde y banda oscura para leerse sobre cualquier footage). Es la <b>palanca nº1 de retención</b> en TikTok/Reels: para el scroll antes de que arranque la voz.</p>
      <h3>Música por mood</h3>
      <p>Gemini elige el <code>music_mood</code> y se toma una pista de <code>music/&lt;mood&gt;/</code> (Incompetech, CC-BY). Moods disponibles:</p>
      <p><code>epic</code> · <code>medieval</code> · <code>mystery</code> · <code>horror</code> · <code>tech</code> · <code>upbeat</code> · <code>happy</code> · <code>emotional</code> · <code>chill</code> · <code>dramatic</code></p>
      <h3>Variantes que se producen</h3>
      <table>
        <tr><th>Archivo</th><th>Uso</th></tr>
        <tr><td><code>video_&lt;lang&gt;_vertical.mp4</code></td><td>Master con música + subtítulos → YouTube</td></tr>
        <tr><td><code>video_&lt;lang&gt;_vertical_tiktok.mp4</code></td><td>Sin música, para añadir audio trending en TikTok</td></tr>
        <tr><td><code>video_&lt;lang&gt;_vertical_nosubs.mp4</code></td><td>Sin subtítulos quemados (TikTok/Reels los autogeneran)</td></tr>
        <tr><td><code>share_&lt;lang&gt;.mp4</code></td><td>Comprimido ~12 MB para enviar por Telegram/cross-post</td></tr>
      </table>
    </div>

    <!-- ══════════════ PARTE C · OPERACIÓN ══════════════ -->

    <h2 id="telegram"><span class="num">10</span>Conexión con Telegram</h2>
    <div class="card">
      <p>El <b>bot</b> (<code>videogen bot</code>) es un proceso en tu ordenador conectado a los servidores de Telegram por <i>long polling</i>: cada pocos segundos pregunta "¿hay mensajes nuevos?". Hace de <b>puente</b> entre la nube de Telegram y tu máquina, donde corre el pipeline.</p>
      <div class="flow">Tú (móvil) ──escribes idea──▶ Telegram (nube)
                                  │  el bot (tu Mac) hace polling y la recibe
                                  ▼  ejecuta el pipeline LOCAL (etapas 1–5)
Tú (móvil) ◀──te envía previews─ bot
                                  │  pulsas "✓ Subir"
                                  ▼  sube a YouTube + 🔔 te notifica el link</div>
      <h3>Qué se necesita técnicamente</h3>
      <ul>
        <li><b>Token del bot</b> (de <code>@BotFather</code>) en <code>.env</code> → identifica el bot ante Telegram.</li>
        <li><b>Tu chat id</b> en <code>.env</code> → para enviarte el resumen diario y las notificaciones.</li>
        <li>El proceso <code>videogen bot</code> <b>corriendo</b> (en la Mac o en el servidor).</li>
      </ul>
      <h3>El resumen diario</h3>
      <p>Cada día a las <span class="kbd">11:00</span> (configurable con <code>TELEGRAM_DAILY_HOUR</code>) el bot te manda automáticamente: tus <b>stats</b> (suscriptores, views) + varias <b>ideas frescas</b> de vídeo. Es tu "redacción matutina".</p>
    </div>

    <h2 id="subida"><span class="num">11</span>Subida automática a YouTube</h2>
    <div class="card">
      <p><b>YouTube es 100% automático</b> vía la Data API v3 con OAuth:</p>
      <div class="step"><div class="n">1</div><div class="b"><b>Autorización única</b> en el navegador (consentimiento de Google, scopes <code>youtube.upload</code> + <code>youtube.readonly</code>) → se guarda un token en <code>secrets/youtube_token.json</code>.</div></div>
      <div class="step"><div class="n">2</div><div class="b"><b>Cada subida</b> reutiliza ese token (se auto-renueva). Envía el MP4 con título, descripción, hashtags y privacidad, marcado como Short.</div></div>
      <div class="step"><div class="n">3</div><div class="b"><b>Notificación a Telegram</b> con el link al terminar; el vídeo pasa de <code>pending/</code> a <code>uploaded/</code> y se guardan los IDs para las stats.</div></div>
      <h3>Publicación programada</h3>
      <p>Puedes <b>programar</b> el Short en vez de publicarlo al instante: se sube <b>privado</b> con un <code>publishAt</code> y YouTube lo hace público solo a esa hora.</p>
      <ul>
        <li><b>Web:</b> en la revisión, elige fecha/hora en el selector y pulsa <span class="kbd">🗓 Programar</span>.</li>
        <li><b>Bot:</b> botón <span class="kbd">🗓 Programar</span> con slots rápidos (hoy/mañana · 14:00 o 21:00, los picos de Shorts).</li>
      </ul>
      <div class="callout warn"><b>Calidad:</b> al subir, YouTube muestra una versión de baja resolución <b>mientras procesa el HD</b> (de minutos a horas). El archivo enviado es 1080p — solo hay que esperar y refrescar.</div>
    </div>

    <h2 id="crosspost"><span class="num">12</span>Cross-posting a otras redes</h2>
    <div class="card">
      <p>TikTok, Instagram, Facebook, Pinterest y Snapchat <b>no ofrecen API gratuita</b> de publicación sin aprobación business. Solución <b>semi-manual</b> (dos toques): el botón <span class="tag">🔁 Cross-post</span> prepara todo por ti.</p>
      <ul>
        <li>Te entrega el archivo adecuado (<code>share</code> comprimido, o la variante <b>sin subtítulos</b> porque esas apps los autogeneran).</li>
        <li>Copia el <b>caption</b> (título + hashtags + tags de alcance: #fyp #parati #reels…) al portapapeles.</li>
        <li>Abre los uploaders web de cada red.</li>
      </ul>
      <table>
        <tr><th>Red</th><th>Nota</th></tr>
        <tr><td>TikTok</td><td>Añade audio trending a volumen bajo (tu voz manda)</td></tr>
        <tr><td>Instagram / Facebook Reels</td><td>Crear → Reel</td></tr>
        <tr><td>Pinterest</td><td>Pin de vídeo</td></tr>
        <tr><td>Snapchat Spotlight</td><td>Mejor desde la app móvil</td></tr>
      </table>
      <div class="callout warn">Al "Compartir" un vídeo de Telegram directamente a Instagram, va a <b>Stories</b> (que cortan a 15s). Para un Reel completo: guarda el vídeo en la galería y súbelo desde la app con <span class="kbd">+</span> → Reel.</div>
    </div>

    <h2 id="comandos"><span class="num">13</span>Comandos del bot</h2>
    <div class="card">
      <table>
        <tr><th>Comando</th><th>Qué hace</th></tr>
        <tr><td><i>(escribir una idea)</i></td><td>Genera el vídeo bilingüe a partir de tu frase</td></tr>
        <tr><td><code>/ideas</code></td><td>Propone ideas de dinero <b>específicas</b> (no genéricas), vía Gemini</td></tr>
        <tr><td><code>/send</code> [hint]</td><td>Envía el vídeo más reciente (o el que case con hint) con sus dos variantes + caption copiable</td></tr>
        <tr><td><code>/snapshot</code></td><td>Toma snapshot + manda las gráficas de analytics por plataforma</td></tr>
        <tr><td><code>/stats</code></td><td>Suscriptores del canal + views/likes por vídeo</td></tr>
        <tr><td><code>/optimal</code></td><td>Mejores franjas horarias para publicar</td></tr>
        <tr><td><code>/ui</code></td><td>Enlace a esta web (Studio + Docs)</td></tr>
        <tr><td><code>/help</code></td><td>Ayuda completa con todos los comandos</td></tr>
      </table>
      <h3>Lenguaje natural (no solo comandos)</h3>
      <p>El bot tiene un clasificador NLU (Gemini) que entiende peticiones casuales:</p>
      <ul>
        <li>«envíame el del iPhone con y sin subs» → manda los archivos + caption</li>
        <li>«qué tengo programado» / «lista» → últimos vídeos con estado</li>
        <li>«tt del iphone 897 11» / «ig pulpo 230 2» → registro manual de stats TikTok/Instagram</li>
        <li>«gráficas» / «cómo van los números» → envía las gráficas de analytics</li>
        <li>Cualquier otra frase → genera un vídeo sobre ese tema (default)</li>
      </ul>
      <p>Tras generar, cada preview trae botones: <b>✓ Subir a YouTube</b>, <b>🔁 Cross-post</b>, <b>🗑 Borrar</b>.</p>
      <div class="callout">Regla del proyecto: cada vez que se añade un comando o función, se actualiza <code>/help</code> para que siempre lo refleje.</div>
    </div>

    <h2 id="siempre"><span class="num">14</span>Que funcione siempre</h2>
    <div class="card">
      <p>El bot solo responde si <b>el ordenador está encendido</b> y <b>el proceso del bot corre</b>. Si apagas la Mac, los mensajes <b>esperan en Telegram</b> y se procesan cuando el bot vuelve (no se pierden).</p>
      <table>
        <tr><th>Requisito</th><th>Por qué</th></tr>
        <tr><td>Mac (o servidor) encendida</td><td>El pipeline (ffmpeg, Pillow…) corre en local</td></tr>
        <tr><td><code>videogen bot</code> activo</td><td>Es quien escucha Telegram</td></tr>
        <tr><td>API keys válidas</td><td>Gemini · Pexels · Telegram</td></tr>
        <tr><td>OAuth de YouTube vigente</td><td>Para subir (se auto-renueva con el refresh token)</td></tr>
        <tr><td>Conexión a internet</td><td>Para hablar con todas las APIs</td></tr>
      </table>
      <p>Arrancar el bot a mano:</p>
      <pre>cd ~/automated-videos
.venv/bin/videogen bot</pre>
      <div class="callout">Para 24/7 <b>sin depender de la Mac</b> → desplegar en un servidor siempre encendido (<a href="#deploy">§15</a>).</div>
    </div>

    <h2 id="deploy"><span class="num">15</span>Despliegue 24/7</h2>
    <div class="card">
      <p>Para que el bot responda a cualquier hora sin tener la Mac encendida, se despliega en un servidor siempre activo. Recomendado: <b>Oracle Cloud Free Tier</b> (instancia gratuita para siempre). Los archivos están listos en <code>deploy/</code>:</p>
      <pre>bash deploy/push.sh &lt;IP&gt; &lt;ssh-key&gt;</pre>
      <p>El script instala ffmpeg + dependencias + fuentes + música, copia tus secretos y arranca el bot como servicio <code>systemd</code> (se reinicia solo y sobrevive a reinicios de la máquina). Guía paso a paso en <code>deploy/ORACLE_VM.md</code>.</p>
      <div class="callout warn">Sube los secretos (<code>.env</code>, tokens de YouTube) por <code>scp</code>, nunca al repositorio. Están en <code>.gitignore</code> por seguridad.</div>
    </div>

    <!-- ══════════════ PARTE D · REFERENCIA ══════════════ -->

    <h2 id="archivos"><span class="num">16</span>Estructura de archivos</h2>
    <div class="card">
      <pre>automated-videos/
├─ src/videogen/          código del paquete
│   ├─ script.py          guion con Gemini
│   ├─ voice.py           voz (Edge / ElevenLabs)
│   ├─ visuals.py         clips de Pexels + scoring
│   ├─ wikimedia.py       fotos CC de famosos
│   ├─ graphics.py        overlays de datos (Pillow)
│   ├─ compose.py         montaje con ffmpeg
│   ├─ upload_youtube.py  subida a YouTube
│   ├─ crosspost.py       cross-posting a redes
│   ├─ telegram_bot.py    el bot
│   ├─ webapp.py          la UI web (esta página)
│   └─ service.py         orquesta generate() y publish()
├─ prompts/
│   ├─ niche.md           identidad del nicho de dinero
│   └─ script_system.md   reglas de formato del guion
├─ music/&lt;mood&gt;/*.mp3      música por ánimo (CC-BY)
├─ pending/&lt;slug&gt;/         vídeos generados, sin subir
├─ uploaded/&lt;slug&gt;/        vídeos ya publicados
├─ secrets/               OAuth de YouTube (no se versiona)
├─ deploy/                scripts para el servidor 24/7
└─ .env                   claves y configuración</pre>
      <p>Cada vídeo vive en una carpeta <code>&lt;slug&gt;/</code> con su <code>scripts.json</code>, audios, B-roll, overlays, los MP4 y, tras subir, <code>youtube.json</code> con los links.</p>
    </div>

    <h2 id="config"><span class="num">17</span>Configuración (.env)</h2>
    <div class="card">
      <p>Todas las claves y ajustes viven en <code>.env</code> (gitignored). Las principales:</p>
      <table>
        <tr><th>Variable</th><th>Para qué</th></tr>
        <tr><td><code>GEMINI_API_KEY</code></td><td>Guion e ideas</td></tr>
        <tr><td><code>PEXELS_API_KEY</code></td><td>Clips de stock</td></tr>
        <tr><td><code>TELEGRAM_BOT_TOKEN</code></td><td>El bot (de @BotFather)</td></tr>
        <tr><td><code>TELEGRAM_CHAT_ID</code></td><td>A quién enviar resumen/notificaciones</td></tr>
        <tr><td><code>TELEGRAM_DAILY_HOUR</code></td><td>Hora del resumen diario (ej. <code>11:00</code>)</td></tr>
        <tr><td><code>VOICE_ENGINE</code></td><td><code>edge</code> (gratis, defecto) o <code>elevenlabs</code></td></tr>
        <tr><td><code>EDGE_VOICE_ES</code> / <code>_EN</code></td><td>Voces de Edge por idioma</td></tr>
      </table>
      <div class="callout warn">Nunca pegues estas claves en chats, capturas ni commits. Si una se expone, regenérala en su panel (BotFather / Google AI Studio / Pexels).</div>
    </div>

    <h2 id="recursos"><span class="num">18</span>Recursos y costes</h2>
    <div class="card">
      <table>
        <tr><th>Etapa</th><th>Recurso</th><th>Función</th><th>Coste</th></tr>
        <tr><td>Guion</td><td>Gemini (Google)</td><td>Texto + decisiones (música, famoso, keywords)</td><td><span class="tag">free tier</span></td></tr>
        <tr><td>Voz</td><td>Edge TTS (Microsoft)</td><td>Narración neuronal + timestamps</td><td><span class="tag">ilimitado</span></td></tr>
        <tr><td>Clips</td><td>Pexels</td><td>Vídeo stock de fondo</td><td><span class="tag">gratis</span></td></tr>
        <tr><td>Caras</td><td>Wikimedia Commons</td><td>Fotos CC de famosos + atribución</td><td><span class="tag">gratis</span></td></tr>
        <tr><td>Datos/graphics</td><td>Pillow (local)</td><td>Números grandes, infografías</td><td><span class="tag">local</span></td></tr>
        <tr><td>Música</td><td>Incompetech</td><td>Fondo por mood (CC-BY)</td><td><span class="tag">gratis</span></td></tr>
        <tr><td>Montaje</td><td>ffmpeg (local)</td><td>Ensambla todo → MP4</td><td><span class="tag">local</span></td></tr>
        <tr><td>Subida YT</td><td>YouTube Data API</td><td>Publica</td><td><span class="tag">gratis</span></td></tr>
        <tr><td>Hosting</td><td>Oracle Cloud</td><td>Servidor 24/7</td><td><span class="tag">free tier</span></td></tr>
        <tr><td>Voz premium</td><td>ElevenLabs (opcional)</td><td>Narración más humana</td><td><span class="tag paid">~$5/mes</span></td></tr>
      </table>
      <p><b>Coste por vídeo en la configuración por defecto: ~0 €.</b></p>
    </div>

    <h2 id="ejemplo"><span class="num">19</span>Ejemplo completo paso a paso</h2>
    <div class="card">
      <p>Escribes en el bot: <code>Cuánto gana Cristiano Ronaldo por segundo</code></p>
      <div class="step"><div class="n">1</div><div class="b"><b>Gemini</b> escribe el teaser ("Cristiano Ronaldo gana más de 6€ por segundo, y lo que viene te va a sorprender…"), el hook, 4 datos y el CTA; detecta <code>subject_person = Cristiano Ronaldo</code> y elige <code>music_mood = upbeat</code>; genera título, descripción y hashtags en ES y EN.</div></div>
      <div class="step"><div class="n">2</div><div class="b"><b>Wikimedia</b> baja 3 fotos CC de CR7 (con su atribución) · <b>Pexels</b> baja billetes, estadios y jets según las visual_keywords.</div></div>
      <div class="step"><div class="n">3</div><div class="b"><b>Edge TTS</b> narra en español (voz Álvaro, +10%) y devuelve los timestamps por palabra.</div></div>
      <div class="step"><div class="n">4</div><div class="b"><b>Pillow</b> dibuja overlays "6€ / POR SEGUNDO", "200 M€ / AL AÑO" · <b>ffmpeg</b> monta clips + voz + música upbeat + subtítulos sincronizados.</div></div>
      <div class="step"><div class="n">5</div><div class="b">El bot te manda la preview ES + EN. Revisas, pulsas <b>✓ Subir</b> → se publica en YouTube, recibes el link, y queda listo el botón de cross-post.</div></div>
      <p style="color:var(--muted)">Tiempo total: ~2-3 min · Coste: ~0 €</p>
    </div>

    <h2 id="limites"><span class="num">20</span>Limitaciones honestas</h2>
    <div class="card">
      <ul>
        <li><span class="tag warn">Gemini</span> el free tier tiene límite diario; el sistema reintenta con varios modelos, pero en días muy intensos puede agotarse hasta el reset (medianoche hora del Pacífico).</li>
        <li><span class="tag warn">TikTok</span> la subida y las stats son manuales: no hay API gratuita.</li>
        <li><span class="tag warn">Imágenes IA</span> generar imágenes a medida cuesta dinero → se usa stock + fotos CC (a veces un clip no es perfecto para el tema).</li>
        <li><span class="tag warn">Bot</span> necesita la Mac (o el servidor) encendida para responder.</li>
        <li><span class="tag warn">Voz</span> Edge es muy buena, pero no nivel humano; ElevenLabs (de pago) es superior si lo necesitas.</li>
        <li><span class="tag warn">Datos</span> Gemini puede equivocarse en cifras concretas; conviene revisar datos sensibles antes de publicar.</li>
      </ul>
    </div>

    <h2 id="faq"><span class="num">21</span>Preguntas frecuentes</h2>
    <div class="card">
      <h3>¿El vídeo lo crea una IA de vídeo?</h3>
      <p>No. Se <b>ensambla</b> con material real + voz sintética. La IA genera el guion (Gemini) y la voz (Edge). Así es gratis y el resultado no se ve "artificial".</p>
      <h3>¿Por qué el español rinde más que el inglés?</h3>
      <p>Los datos lo muestran (p. ej. 1.078 vs 4 views en un mismo vídeo). El algoritmo te empuja donde hay tracción. Prioriza ES; usa EN como secundario.</p>
      <h3>¿Por qué la primera vez el vídeo se ve en baja calidad en YouTube?</h3>
      <p>YouTube sirve una versión baja mientras procesa el HD (de minutos a horas). El archivo subido es 1080p; basta esperar y refrescar.</p>
      <h3>¿Puedo poner una canción de moda encima en TikTok?</h3>
      <p>Como tus vídeos son <b>voz narrada</b>, una canción a volumen alto la tapa. Sube la versión con voz+música tal cual, o añade audio trending a volumen muy bajo dejando el "sonido original" alto.</p>
      <h3>¿Por qué al compartir a Reels solo coge 15s?</h3>
      <p>"Compartir" desde Telegram va a Stories (cortan a 15s). Descarga el vídeo a la galería y súbelo desde la app con <span class="kbd">+</span> → Reel.</p>
      <h3>¿Cuánto cuesta operar esto al mes?</h3>
      <p>En la configuración por defecto, prácticamente <b>0 €</b>. Solo pagarías si activas ElevenLabs (~$5) o usas un servidor de pago en vez del free tier de Oracle.</p>
      <h3>¿Qué pasa si Gemini se queda sin cuota un día?</h3>
      <p>El sistema prueba varios modelos de respaldo. Si todos están agotados, espera al reset diario. No se pierde nada: reintentas el prompt después.</p>
    </div>

    <h2 id="glosario"><span class="num">22</span>Glosario</h2>
    <div class="card">
      <table>
        <tr><th>Término</th><th>Significado</th></tr>
        <tr><td>Teaser / cold-open</td><td>Los primeros ~5s que enganchan antes de revelar el contenido</td></tr>
        <tr><td>Hook</td><td>La frase que plantea la curiosidad central del vídeo</td></tr>
        <tr><td>Body</td><td>El desarrollo: los datos curiosos, uno tras otro</td></tr>
        <tr><td>CTA</td><td>Call to action: la llamada final (sigue, comenta…)</td></tr>
        <tr><td>Overlay de datos</td><td>El número/dato grande dibujado sobre el vídeo</td></tr>
        <tr><td>B-roll</td><td>Los clips de stock de fondo (Pexels)</td></tr>
        <tr><td>visual_keywords</td><td>Palabras que Gemini da para buscar el B-roll de cada segmento</td></tr>
        <tr><td>music_mood</td><td>El "ánimo" musical que elige Gemini (epic, upbeat…)</td></tr>
        <tr><td>subject_person</td><td>El famoso del tema → dispara la descarga de fotos CC</td></tr>
        <tr><td>Slug</td><td>El identificador-de-carpeta del vídeo (ej. <code>cr7-gana-por-segundo</code>)</td></tr>
        <tr><td>Variante TikTok</td><td>El MP4 sin música / sin subtítulos para cross-post</td></tr>
        <tr><td>WordBoundary</td><td>El timestamp por palabra que da Edge TTS (para subtítulos)</td></tr>
        <tr><td>Long polling</td><td>Cómo el bot pregunta a Telegram por mensajes nuevos</td></tr>
        <tr><td>OAuth</td><td>La autorización con Google que permite subir a YouTube</td></tr>
        <tr><td>CC / Dominio Público</td><td>Licencias que permiten reusar fotos/música legalmente</td></tr>
        <tr><td>RPM / CPM</td><td>Lo que paga YouTube por mil reproducciones / impresiones</td></tr>
      </table>
    </div>
  </main>
</div></body></html>"""


# ───────────────────────────── ANALYTICS ──────────────────────────────────
ANALYTICS_HTML = f"""<!doctype html><html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>videogen · analytics</title><style>{_CSS}
.hero{{padding:48px 0 18px}}
.eyebrow{{font-family:'JetBrains Mono',monospace;font-size:12px;letter-spacing:3px;text-transform:uppercase;color:var(--gold);margin-bottom:18px}}
.hero h1{{font-family:'Fraunces',serif;font-weight:900;font-size:clamp(36px,5.6vw,64px);line-height:1;letter-spacing:-1.2px;margin:0;color:var(--ink)}}
.hero p{{color:var(--muted);font-size:17px;max-width:620px;margin:16px 0 0}}
.charts{{display:grid;gap:22px;margin-top:18px}}
.chartcard{{background:var(--surface);border:1px solid var(--glassborder);border-radius:18px;padding:18px}}
.chartcard h3{{font-family:'Fraunces',serif;font-weight:600;font-size:18px;margin:0 0 12px;color:var(--ink);letter-spacing:-.3px}}
.chartcard img{{width:100%;height:auto;border-radius:12px;border:1px solid var(--line);background:var(--bg)}}
.chartcard.empty{{text-align:center;color:var(--muted);font-family:'JetBrains Mono',monospace;font-size:13px;padding:36px}}
.row{{display:flex;align-items:center;gap:12px;flex-wrap:wrap}}
.note{{color:var(--muted);font-family:'JetBrains Mono',monospace;font-size:12.5px;margin-top:8px}}
</style></head><body>
<nav><div class="wrap row"><div class="brand"><span class="mark">$</span> videogen</div>
  <div class="navlinks"><a href="/">Studio</a><a href="/analytics" class="active">Analytics</a><a href="/docs">Documentación</a></div></div></nav>
<div class="wrap">
  <header class="hero fade">
    <div class="eyebrow">Analytics · progreso del canal</div>
    <h1>Cómo van <span class="gold-text">tus números.</span></h1>
    <p>Snapshot diario por plataforma: crecimiento del canal, evolución de views por vídeo y like-rate. YouTube e Instagram (si tienes token) automáticos; TikTok manual desde el bot.</p>
    <div class="row" style="margin-top:18px">
      <button class="btn" id="snapBtn" onclick="snap()">📸 Tomar snapshot ahora</button>
      <span id="snapState" class="note"></span>
    </div>
    <p class="note">El resumen diario a las 11:00 también te llega por Telegram.</p>
  </header>
  <section class="charts">
    <article class="chartcard fade" style="animation-delay:.04s">
      <h3>🎥 YouTube</h3>
      <img id="img_youtube" src="/chart/youtube.png" alt="YouTube" onerror="this.parentElement.classList.add('empty');this.style.display='none';this.parentElement.innerHTML='&lt;h3&gt;🎥 YouTube&lt;/h3&gt;Sin datos. Pulsa <b>snapshot</b> arriba.';">
    </article>
    <article class="chartcard fade" style="animation-delay:.08s">
      <h3>🎵 TikTok</h3>
      <img id="img_tiktok" src="/chart/tiktok.png" alt="TikTok" onerror="this.parentElement.classList.add('empty');this.style.display='none';this.parentElement.innerHTML='&lt;h3&gt;🎵 TikTok&lt;/h3&gt;Sin datos. En el bot escribe: «tt iphone 897 11» para registrar manualmente.';">
    </article>
    <article class="chartcard fade" style="animation-delay:.12s">
      <h3>📷 Instagram</h3>
      <img id="img_instagram" src="/chart/instagram.png" alt="Instagram" onerror="this.parentElement.classList.add('empty');this.style.display='none';this.parentElement.innerHTML='&lt;h3&gt;📷 Instagram&lt;/h3&gt;Sin datos. Configura IG Graph API (IG_ACCESS_TOKEN + IG_BUSINESS_ACCOUNT_ID en .env) o registra a mano desde el bot.';">
    </article>
  </section>
  <div class="foot">videogen · analytics · <a href="/docs">cómo funciona →</a></div>
</div>
<script>
async function snap(){{
  const btn=document.getElementById('snapBtn'), st=document.getElementById('snapState');
  btn.disabled=true; st.innerHTML='<span class="spin"></span> tomando snapshot…';
  try{{
    const r=await fetch('/analytics/snapshot',{{method:'POST'}});
    const j=await r.json();
    if(j.ok){{
      st.textContent='✓ snapshot guardado · refrescando…';
      // Refresca cada <img> añadiendo cache-bust
      for(const p of ['youtube','tiktok','instagram']){{
        const el=document.getElementById('img_'+p);
        if(el) el.src='/chart/'+p+'.png?'+Date.now();
      }}
      setTimeout(()=>{{st.textContent='';btn.disabled=false;}},1500);
    }}else{{
      st.textContent='⚠️ '+(j.error||'error'); btn.disabled=false;
    }}
  }}catch(e){{ st.textContent='⚠️ '+e; btn.disabled=false; }}
}}
</script>
</body></html>"""


def _lan_ip() -> str:
    """IP de la Mac en la red local (para acceder desde el móvil)."""
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def run(host: str = "127.0.0.1", port: int = 5005, lan: bool = False):
    import webbrowser

    if lan:
        ip = _lan_ip()
        print(f"📱 Desde el móvil (misma WiFi):  http://{ip}:{port}")
        print(f"💻 En esta Mac:                  http://127.0.0.1:{port}")
        app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
    else:
        webbrowser.open(f"http://{host}:{port}")
        app.run(host=host, port=port, debug=False, threaded=True)

