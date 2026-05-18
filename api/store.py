"""
In-memory data store — loads Parquet on startup, serves aggregated queries.
Falls back to synthetic sample data if no real data is available.
"""

import logging
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

NORMALIZED = Path("data/processed/normalized_trade.parquet")
SAMPLE     = Path("data/processed/sample_trade.parquet")

_df: pd.DataFrame | None = None


def load() -> pd.DataFrame:
    global _df
    if _df is not None:
        return _df

    if NORMALIZED.exists():
        log.info("Loading normalized trade data from %s", NORMALIZED)
        _df = pd.read_parquet(NORMALIZED)
    elif SAMPLE.exists():
        log.info("Loading sample trade data from %s", SAMPLE)
        _df = pd.read_parquet(SAMPLE)
    else:
        log.info("No data file found — generating sample data")
        from utils.sample_data import generate_all_years
        _df = generate_all_years()

    log.info("Loaded %d rows, years %d–%d",
             len(_df),
             int(_df["shamsi_year"].min()),
             int(_df["shamsi_year"].max()))
    return _df


def available_years() -> list[int]:
    return sorted(_df["shamsi_year"].dropna().unique().astype(int).tolist())


# ── Query helpers ────────────────────────────────────────────────────────────

def _filter(df: pd.DataFrame, year: int | None, direction: str | None) -> pd.DataFrame:
    if year:
        df = df[df["shamsi_year"] == year]
    if direction:
        df = df[df["direction"] == direction]
    return df


def summary(year: int | None = None) -> dict:
    df = load()
    if year:
        df = df[df["shamsi_year"] == year]

    def total(d):
        sub = df[df["direction"] == d]
        return {
            "value_usd": float(sub["value_usd"].sum()),
            "weight_kg": float(sub["net_weight_kg"].sum()),
            "rows": int(len(sub)),
        }

    balance = total("export")["value_usd"] - total("import")["value_usd"]

    return {
        "year": year,
        "export": total("export"),
        "import": total("import"),
        "transit": {"weight_kg": float(df[df["direction"] == "transit"]["net_weight_kg"].sum())},
        "trade_balance_usd": balance,
        "available_years": available_years(),
    }


def map_flows(year: int, direction: str, top_n: int = 50) -> list[dict]:
    """Arc data for Deck.gl: one record per country with total value/weight."""
    df = _filter(load(), year, direction)
    df = df[df["country_iso3"].notna()]

    grp = (df.groupby("country_iso3")
             .agg(value_usd=("value_usd", "sum"),
                  weight_kg=("net_weight_kg", "sum"))
             .reset_index()
             .sort_values("value_usd", ascending=False)
             .head(top_n))

    from api.geo import COUNTRY_COORDS
    result = []
    for _, row in grp.iterrows():
        coords = COUNTRY_COORDS.get(row["country_iso3"])
        if not coords:
            continue
        result.append({
            "country": row["country_iso3"],
            "lat": coords[0],
            "lng": coords[1],
            "value_usd": round(float(row["value_usd"] or 0)),
            "weight_kg": round(float(row["weight_kg"] or 0)),
        })
    return result


def timeseries(country: str | None, direction: str | None,
               hs_chapter: int | None) -> list[dict]:
    df = load()
    if country:
        df = df[df["country_iso3"] == country]
    if direction:
        df = df[df["direction"] == direction]
    if hs_chapter:
        df = df[df["hs_chapter"] == hs_chapter]

    grp = (df.groupby("shamsi_year")
             .agg(value_usd=("value_usd", "sum"),
                  weight_kg=("net_weight_kg", "sum"))
             .reset_index()
             .sort_values("shamsi_year"))

    return [
        {"year": int(r["shamsi_year"]),
         "value_usd": round(float(r["value_usd"] or 0)),
         "weight_kg": round(float(r["weight_kg"] or 0))}
        for _, r in grp.iterrows()
    ]


def treemap(year: int, direction: str) -> list[dict]:
    from data.mappings.hs_sections import HS_CHAPTERS
    df = _filter(load(), year, direction)
    df = df[df["hs_chapter"].notna()]

    grp = (df.groupby("hs_chapter")
             .agg(value_usd=("value_usd", "sum"),
                  weight_kg=("net_weight_kg", "sum"))
             .reset_index())

    result = []
    for _, row in grp.iterrows():
        ch = int(row["hs_chapter"])
        meta = HS_CHAPTERS.get(ch, (0, f"Chapter {ch}", f"فصل {ch}"))
        result.append({
            "hs_chapter": ch,
            "section": meta[0],
            "name_en": meta[1],
            "name_fa": meta[2],
            "value_usd": round(float(row["value_usd"] or 0)),
            "weight_kg": round(float(row["weight_kg"] or 0)),
        })

    return sorted(result, key=lambda x: x["value_usd"], reverse=True)


def top_partners(year: int, direction: str, n: int = 15) -> list[dict]:
    from api.geo import COUNTRY_COORDS
    from data.mappings.country_mapping import COUNTRY_META

    df = _filter(load(), year, direction)
    df = df[df["country_iso3"].notna() & (df["direction"] != "transit")]

    grp = (df.groupby("country_iso3")
             .agg(value_usd=("value_usd", "sum"),
                  weight_kg=("net_weight_kg", "sum"))
             .reset_index()
             .sort_values("value_usd", ascending=False)
             .head(n))

    total = grp["value_usd"].sum()
    result = []
    for i, (_, row) in enumerate(grp.iterrows()):
        iso3 = row["country_iso3"]
        meta = COUNTRY_META.get(iso3, {})
        result.append({
            "rank": i + 1,
            "country_iso3": iso3,
            "name_fa": meta.get("name_fa", iso3),
            "name_en": meta.get("name_en", iso3),
            "value_usd": round(float(row["value_usd"] or 0)),
            "weight_kg": round(float(row["weight_kg"] or 0)),
            "share_pct": round(float(row["value_usd"] or 0) / total * 100, 1) if total else 0,
        })
    return result
