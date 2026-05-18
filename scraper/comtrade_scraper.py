"""
UN Comtrade scraper — Iran trade data via the legacy public API.

Endpoint: https://comtrade.un.org/api/get
Iran reporter code: 364
Rate limit: ~100 requests/hour unauthenticated.

Each call returns up to 500 rows; we paginate by commodity section and year.
"""

import time
import logging
from pathlib import Path

import requests
import pandas as pd

log = logging.getLogger(__name__)

COMTRADE_URL = "https://comtrade.un.org/api/get"
IRAN_CODE    = "364"

# HS sections 01-99 broken into groups to stay under 500-row limit per call
HS_SECTIONS = [f"{i:02d}" for i in range(1, 100)]

FLOW_MAP = {"1": "import", "2": "export", "3": "re-export", "4": "re-import"}

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"


def _get(params: dict, retries: int = 3) -> dict | None:
    delay = 4
    for attempt in range(retries):
        try:
            r = requests.get(COMTRADE_URL, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
            # Comtrade returns validation errors in the response body
            if data.get("validation", {}).get("status", {}).get("value") not in (0, None):
                msg = data.get("validation", {}).get("message", {}).get("value", "unknown")
                log.warning("Comtrade API warning: %s", msg)
            return data
        except Exception as e:
            log.warning("Attempt %d/%d failed: %s", attempt + 1, retries, e)
            if attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
    return None


def fetch_iran_annual(year: int, flow: str = "all") -> pd.DataFrame:
    """
    Fetch Iran's total trade for one year, broken down by HS 2-digit chapter.
    flow: '1'=import, '2'=export, 'all'=both
    Returns a DataFrame with canonical column names.
    """
    frames = []
    # Request by HS chapter groups (AG2 = 2-digit aggregation)
    for chapter_start in range(1, 100, 10):
        chapters = ",".join(f"{i:02d}" for i in range(chapter_start, min(chapter_start + 10, 100)))
        params = {
            "r":   IRAN_CODE,
            "px":  "HS",
            "ps":  str(year),
            "rg":  flow,
            "cc":  chapters,
            "fmt": "json",
            "max": 500,
            "head": "H",
        }
        data = _get(params)
        if not data or not data.get("dataset"):
            time.sleep(1)
            continue
        frames.append(pd.DataFrame(data["dataset"]))
        time.sleep(1.2)  # respect rate limit

    if not frames:
        return pd.DataFrame()

    raw = pd.concat(frames, ignore_index=True)
    return _normalize(raw, year)


def _normalize(raw: pd.DataFrame, year: int) -> pd.DataFrame:
    col_map = {
        "rtTitle":    "reporter",
        "ptTitle":    "country_name",
        "cmdCode":    "hs_code",
        "cmdDescE":   "commodity_description",
        "rgCode":     "_flow_code",
        "TradeValue": "value_usd",
        "NetWeight":  "net_weight_kg",
        "yr":         "year",
        "period":     "period",
        "qtCode":     "quantity_unit",
        "TradeQuantity": "quantity",
    }
    raw = raw.rename(columns={k: v for k, v in col_map.items() if k in raw.columns})

    if "_flow_code" in raw.columns:
        raw["direction"] = raw["_flow_code"].astype(str).map(FLOW_MAP).fillna("unknown")
        raw.drop(columns=["_flow_code"], inplace=True)

    if "year" not in raw.columns:
        raw["year"] = year

    raw["source"] = "un_comtrade"
    return raw


def fetch_years(years: list[int], flow: str = "all") -> pd.DataFrame:
    """Fetch multiple years and concatenate."""
    frames = []
    for yr in years:
        log.info("Comtrade: fetching Iran trade for %d ...", yr)
        df = fetch_iran_annual(yr, flow)
        if not df.empty:
            frames.append(df)
            log.info("  → %d rows", len(df))
        else:
            log.warning("  → no data returned for %d", yr)
        time.sleep(2)

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def save_comtrade(years: list[int], out_path: Path | None = None) -> Path:
    """Fetch and save UN Comtrade data for the given years."""
    out_path = out_path or PROCESSED_DIR / "comtrade_iran.parquet"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    df = fetch_years(years)
    if df.empty:
        log.error("Comtrade returned no data")
        return out_path

    df.to_parquet(out_path, index=False)
    log.info("Saved %d Comtrade rows → %s", len(df), out_path)
    return out_path
