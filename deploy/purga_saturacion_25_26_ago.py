"""Purga la saturación de KIO + los 8 test-autogens del 26/08.

Contexto: 25-26/08 el pipeline generó 6 videos del caso KIO consecutivos
(canibalizan views entre sí) y yo disparé 8 autogens manuales probando el
fix de TikTok que subieron test videos que ahora están en 0 views.

Cirugía: dejar los 2 top KIO (1150v + 1082v) y borrar los 4 restantes +
los 8 test de hoy. Total 12 videos.

Uso:
    .venv/bin/python deploy/purga_saturacion_25_26_ago.py         # dry-run
    .venv/bin/python deploy/purga_saturacion_25_26_ago.py --go    # borra
"""
from __future__ import annotations
import json, sys, requests
from pathlib import Path

KILLS = [
    # === 8 test-autogens de HOY (26/08) con 0 views ===
    ("-DyK4lWOU3k", "Caso Koldo — 15M€ de comisiones ocultas"),
    ("yeItkw--J40", "Caso Malaya — 200M€ robados al ayuntamiento"),
    ("U-OzKM50SKA", "Caso Neurona — ¿Fraude electoral o archivo judicial?"),
    ("UPN-awl1N8M", "Caso OPEP — Petróleo ×10 en 1973"),
    ("sRRlyrd6Gow", "OTAN España 1982 — 40 años en la Alianza"),
    ("Y5BewVQGrYk", "Caso del 3% — la gran mordida de la obra pública"),
    ("gsnZFKXJlcc", "Caso 3% — 1.400M€ en comisiones"),
    ("2tF0A-OOWEk", "Caso KIO — 300M€ robados al final"),
    # === 4 KIO duplicados (dejamos 1150v + 1082v) ===
    ("o_I1fQdV26s", "Caso KIO — 300M€ que sacudieron la Bolsa (503v)"),
    ("QgvD87JhNAA", "Caso KIO — 300M€ que hundieron la bolsa (110v)"),
    ("MIk3u_XItbM", "Caso KIO — 300M€ en fraude bursátil (15v)"),
]


def get_access_token() -> str:
    tok = json.load(open(Path(__file__).parent.parent / "secrets" / "youtube_token.json"))
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": tok["client_id"], "client_secret": tok["client_secret"],
        "refresh_token": tok["refresh_token"], "grant_type": "refresh_token"}, timeout=15).json()
    if "access_token" not in r:
        sys.exit(f"❌ refresh fail: {r}")
    info = requests.get(f"https://oauth2.googleapis.com/tokeninfo?access_token={r['access_token']}").json()
    if "youtube.force-ssl" not in info.get("scope", ""):
        sys.exit(f"❌ token sin youtube.force-ssl. Ejecuta `videogen reauth` primero.")
    return r["access_token"]


def main():
    dry_run = "--go" not in sys.argv
    if dry_run:
        print(f"MODO DRY-RUN. Añade --go para ejecutar.\n")
        for vid, title in KILLS:
            print(f"  🗑  {vid}  {title}")
        print(f"\nTotal a borrar: {len(KILLS)} videos")
        print(f"Ejecuta: python3 deploy/purga_saturacion_25_26_ago.py --go")
        return

    access = get_access_token()
    H = {"Authorization": f"Bearer {access}"}
    ok = failed = notfound = 0
    for i, (vid, title) in enumerate(KILLS, 1):
        r = requests.delete(f"https://www.googleapis.com/youtube/v3/videos?id={vid}",
                            headers=H, timeout=15)
        if r.status_code == 204:
            print(f"  [{i:2d}/{len(KILLS)}] ✅ {vid} · {title}")
            ok += 1
        elif r.status_code == 404:
            print(f"  [{i:2d}/{len(KILLS)}] ⚠ 404 {vid} — ya borrado?")
            notfound += 1
        else:
            print(f"  [{i:2d}/{len(KILLS)}] ❌ {r.status_code} {vid} · {r.text[:100]}")
            failed += 1
    print(f"\nResultado: {ok} borrados · {notfound} not-found · {failed} fallos")


if __name__ == "__main__":
    main()
