"""
World Bank API scraper — macroeconomic trade indicators for Iran.

Uses the World Bank REST API (no key required).
Iran ISO2 = IR, ISO3 = IRN.

Key indicators fetched:
  NE.EXP.GNFS.CD   Exports of goods and services (current USD)
  NE.IMP.GNFS.CD   Imports of goods and services (current USD)
  TX.VAL.MRCH.CD.WT Merchandise exports (current USD)
  TM.VAL.MRCH.CD.WT Merchandise imports (current USD)
  NY.GDP.MKTP.CD   GDP (current USD)
  FP.CPI.TOTL.ZG   Inflation (CPI %)
  BN.CAB.XOKA.CD   Current account balance (USD)
"""

import time
import logging
from pathlib import Path

import requests
import pandas as pd

log = logging.getLogger(__name__)

WB_BASE  = "https://api.worldbank.org/v2"
IRAN_ISO = "IRN"

INDICATORS = {
    "NE.EXP.GNFS.CD":    "exports_goods_services_usd",
    "NE.IMP.GNFS.CD":    "imports_goods_services_usd",
    "TX.VAL.MRCH.CD.WT": "merchandise_exports_usd",
    "TM.VAL.MRCH.CD.WT": "merchandise_imports_usd",
    "NY.GDP.MKTP.CD":    "gdp_usd",
    "FP.CPI.TOTL.ZG":    "inflation_cpi_pct",
    "BN.CAB.XOKA.CD":    "current_account_balance_usd",
}

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"


def _fetch_indicator(indicator: str, country: str = IRAN_ISO,
                     start: int = 2000, end: int = 2024) -> list[dict]:
    url = f"{WB_BASE}/country/{country}/indicator/{indicator}"
    params = {
        "format":   "json",
        "per_page": 100,
        "mrv":      end - start + 1,
        "date":     f"{start}:{end}",
    }
    try:
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        payload = r.json()
        # WB returns [metadata, data_array]
        if isinstance(payload, list) and len(payload) == 2:
            return payload[1] or []
    except Exception as e:
        log.warning("World Bank fetch failed for %s: %s", indicator, e)
    return []


def fetch_macro_indicators(start: int = 2000, end: int = 2024) -> pd.DataFrame:
    """
    Fetch all macro trade indicators for Iran and return as a wide DataFrame
    indexed by (country, year).
    """
    rows: dict[int, dict] = {}

    for indicator, col_name in INDICATORS.items():
        log.info("WorldBank: fetching %s (%s) ...", col_name, indicator)
        records = _fetch_indicator(indicator, start=start, end=end)
        for rec in records:
            if rec.get("value") is None:
                continue
            yr = int(rec["date"])
            if yr not in rows:
                rows[yr] = {"year": yr, "country": "Iran", "country_iso3": "IRN",
                            "source": "world_bank"}
            rows[yr][col_name] = rec["value"]
        time.sleep(0.5)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(list(rows.values())).sort_values("year")
    log.info("WorldBank: %d year-rows fetched", len(df))
    return df


def save_worldbank(out_path: Path | None = None,
                   start: int = 2000, end: int = 2024) -> Path:
    """Fetch and save World Bank macro indicators."""
    out_path = out_path or PROCESSED_DIR / "worldbank_iran.parquet"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    df = fetch_macro_indicators(start=start, end=end)
    if df.empty:
        log.error("World Bank returned no data")
        return out_path

    df.to_parquet(out_path, index=False)
    log.info("Saved %d WorldBank rows → %s", len(df), out_path)
    return out_path
