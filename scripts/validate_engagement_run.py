#!/usr/bin/env python3
"""Validador post-catchup: reporta qué engagement corrió y qué falló.

Uso: ./scripts/validate_engagement_run.py

Chequea los 5 ledgers de engagement post-catchup 11 UTC.
Da diagnóstico claro sin abrir Actions UI.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"

CHECKS = [
    ("engagement_ledger.json", "YT auto-reply comentarios"),
    ("ig_engagement_ledger.json", "IG auto-reply reels"),
    ("threads_engagement_ledger.json", "Threads reply-propias"),
    ("bsky_reply_boost_ledger.json", "Bluesky boost trending"),
    ("playlists_manager_ledger.json", "Playlists por case_key"),
]


def _ledger_summary(path: Path) -> str:
    if not path.exists():
        return "❌ NO EXISTE"
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return f"⚠️  parse fail: {e}"
    mt = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    age = datetime.now(timezone.utc) - mt
    hrs = age.total_seconds() / 3600
    age_str = f"{hrs:.1f}h" if hrs < 24 else f"{age.days}d"
    # Métricas útiles según ledger
    replied = d.get("replied", [])
    cases = d.get("cases", {})
    day_count = d.get("day_count", {})
    parts = [f"mtime: hace {age_str}"]
    if isinstance(replied, list):
        parts.append(f"replied: {len(replied)}")
    if isinstance(cases, dict) and cases:
        parts.append(f"cases: {len(cases)}")
    if day_count:
        today = datetime.now(timezone.utc).date().isoformat()
        parts.append(f"hoy: {day_count.get(today, 0)}")
    return "✅ " + " · ".join(parts)


def _last_catchup_commit() -> str:
    try:
        out = subprocess.check_output(
            ["git", "log", "--oneline", "-30"], cwd=ROOT, text=True
        )
        for line in out.splitlines():
            if "snapshot" in line and "[skip ci]" in line:
                return line
        return "no encontrado"
    except Exception as e:
        return f"git fail: {e}"


def main() -> int:
    print("═══ Validación post-catchup engagement ═══\n")
    print(f"Último snapshot CI: {_last_catchup_commit()}\n")
    ok = 0
    fail = 0
    for fn, desc in CHECKS:
        status = _ledger_summary(OUT / fn)
        print(f"  {desc:35s}  {status}")
        if status.startswith("✅"):
            ok += 1
        else:
            fail += 1
    print()
    print(f"  Resumen: {ok}/{len(CHECKS)} ledgers presentes")
    if fail == 0:
        print("  ✅ Todos los engagement corrieron. Chequea Telegram si hubo trabajo real.")
    elif ok == 0:
        print("  🔴 NINGUNO corrió. Probable el catchup 11 UTC no se disparó o falló al inicio.")
        print("     → Revisar: https://github.com/yassinebhk/automated-videos/actions")
    else:
        print(f"  🟡 Parcial. Los {fail} faltantes tienen error de token o bug.")
        print("     → Ver logs del run en Actions para el detalle.")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
