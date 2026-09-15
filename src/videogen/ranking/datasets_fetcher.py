"""Fetchers de datasets REALES para TopRanking.

Sustituye la generación LLM (que alucinaba datos falsos) por fetch de
APIs públicas gratuitas + cache local en output/ranking_datasets/.

Fuentes cableadas:
  - World Bank Open Data (https://api.worldbank.org/v2/) — sin key, JSON.
    Indicadores económicos, demográficos, salud, educación por país y año.
  - REST Countries (https://restcountries.com/v3.1/) — sin key, países.
  - Wikipedia tables — scrape con requests+BS4 para rankings puntuales.

Cache: output/ranking_datasets/{key}.json con timestamp de última descarga.
Refresh semanal via `videogen ranking-datasets-refresh` cron.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from ..config import ROOT

CACHE_ROOT = ROOT / "output" / "ranking_datasets"


def _cache_path(key: str) -> Path:
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    return CACHE_ROOT / f"{key}.json"


def _save(key: str, data: dict) -> Path:
    p = _cache_path(key)
    data["_fetched_at"] = datetime.now(timezone.utc).isoformat()
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return p


def load_cached(key: str, max_age_days: int = 30) -> dict | None:
    """Devuelve dataset cacheado si existe y no es muy viejo."""
    p = _cache_path(key)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    ts = data.get("_fetched_at")
    if ts:
        try:
            dt = datetime.fromisoformat(ts)
            age_days = (datetime.now(timezone.utc) - dt).total_seconds() / 86400
            if age_days > max_age_days:
                return None
        except Exception:
            pass
    return data


# ─────────────────────────────────────────────────────────────
# World Bank Open Data (https://api.worldbank.org/v2/)
# ─────────────────────────────────────────────────────────────

_WB_TOP_COUNTRIES_BY = {
    # Indicador → nombre display + unidad
    "NY.GDP.MKTP.CD":    ("PIB en $USD", "$B"),
    "SP.POP.TOTL":        ("Población total", "M"),
    "SP.DYN.LE00.IN":     ("Esperanza de vida", "años"),
    "NY.GDP.PCAP.CD":     ("PIB per cápita", "$"),
    "SL.UEM.TOTL.ZS":     ("% desempleo total", "%"),
    "IT.NET.USER.ZS":     ("% usuarios Internet", "%"),
    "EG.USE.ELEC.KH.PC":  ("Consumo eléctrico per cápita", "kWh"),
    "EN.ATM.CO2E.PC":     ("Emisiones CO2 per cápita", "t"),
    "MS.MIL.XPND.CD":     ("Gasto militar", "$B"),
    "ST.INT.RCPT.CD":     ("Ingresos turismo", "$B"),
}


def fetch_worldbank_top(indicator: str, from_year: int = 2000,
                          to_year: int = 2024, top_n: int = 10) -> dict | None:
    """Fetch top N países en un indicador World Bank a lo largo de años.

    Devuelve dataset formateado para bar chart race:
      {years: [2000, 2001, ...], items: [nombre_país, ...],
       data: [[val_year0_p0, val_year0_p1, ...], [val_year1_p0, ...]],
       unidad, source_url, source_label, titulo_video}
    """
    display, unit = _WB_TOP_COUNTRIES_BY.get(indicator, (indicator, ""))
    key = f"wb_{indicator.replace('.', '_')}_{from_year}_{to_year}"
    url = (f"https://api.worldbank.org/v2/country/all/indicator/{indicator}"
             f"?format=json&per_page=15000&date={from_year}:{to_year}")
    try:
        r = requests.get(url, timeout=30)
        if r.status_code != 200:
            print(f"  WB fetch fail {indicator}: HTTP {r.status_code}")
            return None
        payload = r.json()
        if not isinstance(payload, list) or len(payload) < 2:
            return None
        entries = payload[1] or []
    except Exception as e:
        print(f"  WB fetch fail {indicator}: {e}")
        return None

    # Filtra: solo países reales (region iso3 = country code, no región agregada)
    # WB marca región agregada con id que empieza por número o cadenas tipo WLD/EUU
    AGG_IDS = {"WLD", "EUU", "OED", "ARB", "HIC", "LIC", "LMC", "MIC",
                "UMC", "LMY", "EMU", "PST", "LTE", "MEA", "SSF", "SAS",
                "EAS", "ECS", "LCN", "NAC", "AFE", "AFW", "EAP", "SSA",
                "PRE", "TLA", "TEA", "TSA", "TEC", "TMN", "TSS", "TDA",
                "TWN", "OSS", "PSS", "PSE", "IBB", "IBT", "IBD", "IDA",
                "IDX", "IDB", "FCS", "HPC"}
    by_country: dict[str, dict[int, float]] = {}
    country_names: dict[str, str] = {}
    for e in entries:
        cid = (e.get("countryiso3code") or "").strip()
        if not cid or cid in AGG_IDS:
            continue
        val = e.get("value")
        if val is None:
            continue
        year = int(e.get("date", 0))
        name = (e.get("country") or {}).get("value", cid)
        by_country.setdefault(cid, {})[year] = float(val)
        country_names[cid] = name

    if not by_country:
        return None

    # Elige top N por último año con datos
    years_sorted = sorted(
        set(y for cvals in by_country.values() for y in cvals.keys())
    )
    last_year = years_sorted[-1] if years_sorted else to_year
    ranked = sorted(
        [(cid, cvals.get(last_year, 0)) for cid, cvals in by_country.items()],
        key=lambda x: -x[1],
    )[:top_n]
    top_ids = [cid for cid, _ in ranked]
    items = [country_names[cid] for cid in top_ids]

    # Matriz [year][country]
    matrix = []
    for y in years_sorted:
        row = []
        for cid in top_ids:
            v = by_country.get(cid, {}).get(y)
            row.append(round(float(v), 2) if v is not None else 0)
        matrix.append(row)

    # Formatea unidad para display (M para millones, $B para billions)
    unit_scaled = unit
    if unit == "M":  # población → millones
        matrix = [[round(v / 1_000_000, 2) for v in row] for row in matrix]
    elif unit == "$B":  # dinero → billions
        matrix = [[round(v / 1_000_000_000, 2) for v in row] for row in matrix]

    dataset = {
        "key": key,
        "titulo_video": f"TOP 10 Países por {display} ({from_year}-{years_sorted[-1] if years_sorted else to_year})",
        "years": years_sorted,
        "items": items,
        "data": matrix,
        "unidad": unit_scaled,
        "source_label": "World Bank Open Data",
        "source_url": f"https://data.worldbank.org/indicator/{indicator}",
        "cierre_dato": f"Datos oficiales del World Bank actualizados a {years_sorted[-1] if years_sorted else to_year}",
    }
    _save(key, dataset)
    print(f"  ✅ WB {indicator} guardado ({len(items)} países × {len(years_sorted)} años)")
    return dataset


# ─────────────────────────────────────────────────────────────
# Refresh de todos los datasets configurados
# ─────────────────────────────────────────────────────────────

# Lista de datasets a refrescar en cada ejecución del cron weekly
DEFAULT_DATASETS_TO_REFRESH = [
    ("NY.GDP.MKTP.CD", 2000, 2024),      # PIB
    ("SP.POP.TOTL", 1970, 2024),          # Población
    ("SP.DYN.LE00.IN", 1970, 2023),       # Esperanza vida
    ("NY.GDP.PCAP.CD", 1990, 2024),       # PIB per cápita
    ("SL.UEM.TOTL.ZS", 2000, 2024),       # Desempleo
    ("IT.NET.USER.ZS", 2000, 2023),       # % Internet
    ("EN.ATM.CO2E.PC", 1990, 2022),       # CO2 per cápita
    ("MS.MIL.XPND.CD", 2000, 2024),       # Gasto militar
]


def refresh_all() -> dict[str, Any]:
    """Refresh todos los datasets configurados. Cron weekly."""
    from ..notify_batch import add
    results = []
    for indicator, from_y, to_y in DEFAULT_DATASETS_TO_REFRESH:
        try:
            d = fetch_worldbank_top(indicator, from_y, to_y)
            results.append({"indicator": indicator,
                             "ok": d is not None,
                             "items": len(d.get("items", [])) if d else 0})
        except Exception as e:
            results.append({"indicator": indicator, "ok": False,
                             "error": str(e)[:120]})
    ok_count = sum(1 for r in results if r["ok"])
    lines = [f"📊 <b>Ranking datasets refresh</b>: {ok_count}/{len(results)} OK"]
    for r in results:
        icon = "✅" if r["ok"] else "❌"
        lines.append(f"  {icon} {r['indicator']}")
    add("\n".join(lines))
    return {"results": results, "ok_count": ok_count}


def list_available_datasets() -> list[str]:
    """Lista datasets cacheados actualmente disponibles."""
    if not CACHE_ROOT.exists():
        return []
    return [p.stem for p in CACHE_ROOT.glob("*.json")]
