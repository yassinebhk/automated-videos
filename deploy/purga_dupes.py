"""Purga los videos duplicados del canal WaitWhy detectados en la auditoría 30/07.

Contexto: el canal tenía 9 Mario Condes, 9 Colzas, 7 EREs, 5 Preferentes… todos
distintos long-forms del mismo caso porque el dedup keyword list fue insuficiente
antes del fix del 26/07. Estos históricos siguen canibalizando views entre sí y
proyectan "content farm" a nuevos visitantes.

Cirugía: para cada caso, dejar el video con MÁS views y borrar el resto.
Total: 33 videos (todos long-form + 4 shorts atomizados duplicados literales).

Uso:
    .venv/bin/python deploy/purga_dupes.py         # confirmación previa
    .venv/bin/python deploy/purga_dupes.py --go    # ejecuta borrado real

Requiere token con scope youtube.force-ssl (ya activo).
"""
from __future__ import annotations
import json, sys, requests
from pathlib import Path

# Cada tupla = (video_id, título abreviado — para log)
# Todos los KEEP (que NO están aquí) son los de más views por caso.
KILLS = [
    # Bankia — mantenemos "Bankia: El megafraude que arruinó a 300.000" (613v)
    ("FimSmiNSOVA", "BANKIA: 22.400 MILLONES Y EL GRAN ENGAÑO"),
    # Bárcenas — mantenemos "40M€ del PP en Suiza" (745v)
    ("brhke6BykeU", "Bárcenas: 40 Millones en la Caja B del PP"),
    # Colza (8 duplicados!) — mantenemos "Veneno que Mató a 300" (868v)
    ("tJ0py3XaKjk", "Colza — Fraude que Mató a 300"),
    ("Q9ix_JrUxL8", "Colza 1981: 300 Muertos"),
    ("lei77freK_0", "Aceite Colza: 300 Muertes por Estafa"),
    ("_XrwINNW0W4", "Timo aceite colza que mató a 300"),
    ("VpFEEl4xGlI", "Veneno 1981: estafa aceite colza"),
    ("8cNLkJ1qQpo", "Timo aceite colza 1981"),
    ("QeTLayEEuN4", "300 Muertos por Aceite: Colza que España Olvidó"),
    # ERE — mantenemos "ERE de Andalucía: 680M robados" (840v)
    ("YM2Neq9U4Xs", "ERE Andalucía: 680 millones ROBADOS"),
    # Fórum — mantenemos "La gran estafa de los sellos" (770v)
    ("DJDWDy-KKGc", "Fórum Filatélico: estafa de los 4.000 millones"),
    ("z6_0Ujn2TOE", "Fórum Filatélico: estafa de 2.000M€"),
    # Gürtel — mantenemos "PP se financió ilegalmente" (805v)
    ("qxbDG2-kZU8", "Gürtel: saqueó 120 millones"),
    # Mario Conde (8 duplicados!) — mantenemos "8.000 millones y salió libre" (834v)
    ("irRbyY4_jIs", "Mario Conde: desvió 7.000M Banesto"),
    ("wF3zGy3F2Wc", "Mario Conde: robo 8.000M libertad"),
    ("KFg58w4aXh4", "Mario Conde: 8.000M robados casi libre"),
    ("YOuF92pkDYY", "Mario Conde: Fraude 8.000M Nadie Entendió"),
    ("-D8d3T4fF_o", "Mario Conde: 48M€ Banesto"),
    ("qOaDoU2ZnCM", "El Robo 8.000M España Olvidó Banesto"),
    ("DqbzWzBGvnY", "Mario Conde: 8.000M Impunidad"),
    # Preferentes — mantenemos "arruinó a 600.000 españoles" (805v)
    ("-t2fJarrdBk", "Bankia estafó 600.000 españoles preferentes"),
    ("TJ6vPVDFAD4", "Preferentes: Gran Estafa Bancaria"),
    ("NY6OU9f4l5I", "Las Preferentes: 25.000M nadie pagó"),
    ("JRONlMpLlks", "Preferentes: engaño masivo arruinó España"),
    # Ruiz-Mateos/RUMASA (7 duplicados!) — mantenemos "160.000 Millones Pesetas" (911v)
    ("lyUrypqCkfk", "RUMASA: eludió cárcel 2.000M€"),
    ("nqBKy3iKgV8", "RUMASA: 9.000 millones Estado pagó"),
    ("fEkcwJxS1yE", "Ruiz-Mateos 337M€ sin cárcel"),
    ("rX4JO9MX3uA", "Ruiz-Mateos 300.000M España"),
    ("4gVF3cZAgb8", "Expropiación Rumasa primer fraude"),
    # Shorts atomizados duplicados literales (mismo título repetido en distinto video)
    ("6NiDjkEmuGM", "SHORT: La Intervención y el Escándalo 👀"),
    ("bJe9gwR756Q", "SHORT: El Laberinto Judicial 👀"),
    ("KbRy2hfsId8", "SHORT: El agujero negro 👀"),
    ("FhZbY7iw3sA", "SHORT: El Ascenso Meteórico 👀"),
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
        print(f"Ejecuta: python3 deploy/purga_dupes.py --go")
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
            print(f"  [{i:2d}/{len(KILLS)}] · {vid} · (ya no existe) {title}")
            notfound += 1
        else:
            print(f"  [{i:2d}/{len(KILLS)}] ❌ {vid} · status={r.status_code} · {r.text[:150]}")
            failed += 1
    print(f"\n=== RESULTADO ===")
    print(f"  Borrados:    {ok}")
    print(f"  Ya no estaban: {notfound}")
    print(f"  Fallaron:    {failed}")


if __name__ == "__main__":
    main()
