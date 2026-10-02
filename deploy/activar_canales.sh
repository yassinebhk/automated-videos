#!/usr/bin/env bash
# Activa los canales nuevos en 1 paso. TÚ solo haces clic en el navegador y eliges
# el canal correcto; el script reutiliza el client OAuth principal y sube los 3
# secrets a GitHub automáticamente. Uso:
#   bash deploy/activar_canales.sh              # todos los pendientes
#   bash deploy/activar_canales.sh YT_STOIC     # solo uno (recomendado empezar así)
set -uo pipefail
cd "$(dirname "$0")/.."

VENV=".venv/bin/videogen"
[ -x "$VENV" ] || VENV="videogen"

# prefijo → nombre del canal a elegir en el navegador (compatible bash 3.2)
nombre_canal() {
  case "$1" in
    YT_STOIC)        echo "Stoic Mind" ;;
    YT_MISTERIOS)    echo "Enigmas sin Resolver" ;;
    YT_SESGOS)       echo "Mente Racional" ;;
    YT_FILOSOFIA)    echo "Abismo" ;;
    YT_CURIOSIDADES) echo "¿Qué Pasaría Si?" ;;
    YT_ESPACIO)      echo "Cosmos" ;;
    YT_GEOQUIZ)      echo "GeoQuiz" ;;
    *)               echo "$1" ;;
  esac
}
ORDER=(YT_STOIC YT_MISTERIOS YT_SESGOS YT_FILOSOFIA YT_CURIOSIDADES YT_ESPACIO YT_GEOQUIZ)

# client OAuth principal (reutilizado para todos)
read -r CID CSEC < <(python3 - <<'PY'
import json
d=json.load(open("secrets/youtube_client_secret.json"))
k="installed" if "installed" in d else ("web" if "web" in d else list(d)[0])
print(d[k]["client_id"], d[k]["client_secret"])
PY
)
if [ -z "${CID:-}" ]; then echo "❌ No pude leer secrets/youtube_client_secret.json"; exit 1; fi

TARGETS=("$@"); [ ${#TARGETS[@]} -eq 0 ] && TARGETS=("${ORDER[@]}")

for PX in "${TARGETS[@]}"; do
  echo ""
  echo "══════════════════════════════════════════════════════════"
  CN="$(nombre_canal "$PX")"
  echo "  CANAL: $CN   ($PX)"
  echo "  → Cuando se abra el navegador, ELIGE ESTE CANAL: $CN"
  echo "══════════════════════════════════════════════════════════"
  read -r -p "  Enter para abrir el login (o escribe 'skip' para saltarlo): " ans
  [ "$ans" = "skip" ] && { echo "  (saltado)"; continue; }

  "$VENV" reauth --channel "$PX" || { echo "  ⚠️ reauth falló para $PX, sigo con el siguiente"; continue; }

  TOK="output/.reauth_token_${PX}.txt"
  if [ ! -s "$TOK" ]; then echo "  ⚠️ no se generó token para $PX"; continue; fi

  gh secret set "${PX}_REFRESH_TOKEN" < "$TOK" \
    && gh secret set "${PX}_CLIENT_ID" -b "$CID" \
    && gh secret set "${PX}_CLIENT_SECRET" -b "$CSEC" \
    && echo "  ✅ $PX ACTIVADO (3 secrets subidos a GitHub)" \
    || echo "  ⚠️ fallo subiendo secrets de $PX (¿gh logueado?)"
done

echo ""
echo "Hecho. Secrets actuales de canales nuevos:"
gh secret list 2>/dev/null | grep -E "STOIC|MISTERIOS|SESGOS|FILOSOFIA|CURIOSIDADES|ESPACIO|GEOQUIZ" || true
echo "En el próximo catchup (4×/día) los canales con sus 3 secrets suben solos."
