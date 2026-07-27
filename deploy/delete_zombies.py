"""Borra los 27 videos zombi del desastre 26/07 (y anteriores) en YT.

Requiere token con scope youtube.force-ssl. Ejecutar tras `videogen reauth`
con SCOPES actualizados (upload_youtube.py línea 15).
"""
import json, sys, requests
from pathlib import Path

ZOMBIES = [
    # (video_id, título — para log solamente)
    ("xSnjl3ijfxM", "El Veneno en la Cocina 👀"),
    ("vqLZaihkXe4", "La Epidemia Silenciosa 👀"),
    ("syIKo57DGGk", "Los Culpables del Timo 👀"),
    ("myNKVyIIomk", "Décadas de Justicia Lenta 👀"),
    ("x4Rg0kKLgi0", "El Legado de una Herida Abierta 👀"),
    ("LKeryf00EEU", "El Imperio Ruiz-Mateos 👀"),
    ("FCW80wv6P4w", "La Gran Intervención 👀"),
    ("JrUDKJfa6jo", "El Escándalo Judicial 👀"),
    ("wlGBujCEyvU", "La Nueva Rumasa 👀"),
    ("2Go2LRxibe0", "La Promesa Irresistible 👀 #1"),
    ("0RPjp64tmgc", "La Pirámide Perfecta 👀"),
    ("k5d88FKw_Ik", "El Imperio de Briones 👀"),
    ("hA_lLoOQC7M", "El Estallido y la Caída 👀"),
    ("WAf_uommfXM", "Justicia Tardia y Amarga 👀"),
    ("qzr5haV5n_M", "El inicio del envenenamiento 👀"),
    ("2shubNORsoI", "El fraude silencioso 👀"),
    ("SgrjhgYZkpo", "Víctimas y secuelas permanentes 👀"),
    ("Jr-fltzQQlo", "La lenta rueda de la justicia 👀"),
    ("ti9YzBeSSss", "La Promesa Irresistible 👀 #2"),
    ("AeDE3qTGn-8", "RUMASA: La Gran Estafa 135.000M"),
    ("KVVXAkag1Mo", "Gürtel: PP desvió millones con Correa"),
    ("SF2H-ulyTs4", "El juicio del siglo 👀"),
    ("d6dsIN9qJJE", "Aceite de Colza: 300 Muertes"),
    ("maxdLPBCMRE", "Gescartera: 88 Millones"),
    ("5IhnFcWCrx0", "AFINSA: 3.000 Millones"),
    ("_w52elcS0Eo", "Fórum Filatélico: 3.700 Millones"),
    ("SEJ88w7b1Iw", "Gürtel: 330M salpicó al PP"),
]

def get_access_token():
    tok = json.load(open(Path(__file__).parent.parent / "secrets" / "youtube_token.json"))
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": tok["client_id"], "client_secret": tok["client_secret"],
        "refresh_token": tok["refresh_token"], "grant_type": "refresh_token"}, timeout=15).json()
    if "access_token" not in r:
        sys.exit(f"❌ refresh fail: {r}")
    # Verificar scope
    info = requests.get(f"https://oauth2.googleapis.com/tokeninfo?access_token={r['access_token']}").json()
    scopes = info.get("scope", "")
    if "youtube.force-ssl" not in scopes:
        sys.exit(f"❌ token sin youtube.force-ssl. Scopes: {scopes}\n"
                 f"Ejecuta primero `videogen reauth` (tras merged de upload_youtube.py:15)")
    return r["access_token"]


def main():
    access = get_access_token()
    H = {"Authorization": f"Bearer {access}"}
    ok = failed = notfound = 0
    for vid, title in ZOMBIES:
        r = requests.delete(f"https://www.googleapis.com/youtube/v3/videos?id={vid}",
                            headers=H, timeout=15)
        if r.status_code == 204:
            print(f"  ✅ {vid} · {title}")
            ok += 1
        elif r.status_code == 404:
            print(f"  · {vid} · (ya borrado) {title}")
            notfound += 1
        else:
            print(f"  ❌ {vid} · status={r.status_code} · {r.text[:150]}")
            failed += 1
    print(f"\n=== RESULTADO ===")
    print(f"  Borrados:    {ok}")
    print(f"  Ya no estaban: {notfound}")
    print(f"  Fallaron:    {failed}")


if __name__ == "__main__":
    main()
