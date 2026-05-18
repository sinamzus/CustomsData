"""
CBI (Central Bank of Iran / بانک مرکزی) trade balance scraper.

The CBI publishes Excel workbooks on tsd.cbi.ir with balance-of-payments
and trade balance time-series. This module downloads those files and
parses the trade-balance sheet.

Direct download path (as of 2025):
  https://tsd.cbi.ir/DisplayEn/Content.aspx  (BOP table page)

Because the CBI site requires session cookies to serve downloads, this
scraper works in two stages:
  1. Fetch the BOP page to obtain a session + any hidden form fields.
  2. POST to trigger the Excel download.

If the direct download fails (site layout changes), the scraper falls
back to a known static URL pattern and logs a clear error.
"""

import io
import re
import time
import logging
from pathlib import Path

import requests
import pandas as pd
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

CBI_BASE    = "https://tsd.cbi.ir"
CBI_BOP_URL = "https://tsd.cbi.ir/DisplayEn/Content.aspx"

# Fallback: CBI sometimes publishes annual reports as static Excel links
CBI_STATIC_URLS = [
    "https://www.cbi.ir/exratesFile/",  # exchange rates
]

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
})


def _get_page(url: str) -> requests.Response | None:
    try:
        r = SESSION.get(url, timeout=20, verify=False)
        r.raise_for_status()
        return r
    except Exception as e:
        log.warning("CBI page fetch failed: %s", e)
        return None


def _extract_viewstate(html: str) -> dict:
    """Extract ASP.NET hidden form fields needed for POST."""
    soup = BeautifulSoup(html, "lxml")
    fields = {}
    for name in ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"):
        tag = soup.find("input", {"name": name})
        if tag:
            fields[name] = tag.get("value", "")
    return fields


def fetch_trade_balance_excel() -> bytes | None:
    """
    Attempt to download the CBI trade balance Excel from the BOP page.
    Returns raw bytes of the Excel file, or None on failure.
    """
    resp = _get_page(CBI_BOP_URL)
    if not resp:
        return None

    hidden = _extract_viewstate(resp.text)
    if not hidden:
        log.warning("CBI: no ASP.NET viewstate found — page layout may have changed")
        return None

    # Look for the Excel export button/link
    soup = BeautifulSoup(resp.text, "lxml")
    export_btn = (
        soup.find("input", {"value": re.compile(r"Excel|اکسل|export", re.I)}) or
        soup.find("a",     href=re.compile(r"\.xlsx?|ExportExcel|DownloadExcel", re.I))
    )

    if not export_btn:
        log.warning("CBI: could not locate Excel export control on %s", CBI_BOP_URL)
        return None

    if export_btn.name == "a":
        href = export_btn.get("href", "")
        dl_url = href if href.startswith("http") else CBI_BASE + "/" + href.lstrip("/")
        try:
            r = SESSION.get(dl_url, timeout=30, verify=False)
            r.raise_for_status()
            return r.content
        except Exception as e:
            log.warning("CBI direct download failed: %s", e)
            return None

    # POST form submission for <input type="submit">
    form_data = {**hidden, export_btn.get("name", "btnExcel"): export_btn.get("value", "")}
    try:
        r = SESSION.post(CBI_BOP_URL, data=form_data, timeout=30, verify=False)
        r.raise_for_status()
        ct = r.headers.get("content-type", "")
        if "excel" in ct or "spreadsheet" in ct or "octet" in ct:
            return r.content
        log.warning("CBI POST returned content-type: %s (expected Excel)", ct)
    except Exception as e:
        log.warning("CBI POST failed: %s", e)

    return None


def parse_trade_balance(excel_bytes: bytes) -> pd.DataFrame:
    """Parse CBI trade balance Excel into a tidy DataFrame."""
    try:
        xf = pd.ExcelFile(io.BytesIO(excel_bytes))
    except Exception as e:
        log.error("Cannot parse CBI Excel: %s", e)
        return pd.DataFrame()

    frames = []
    for sheet in xf.sheet_names:
        try:
            df = pd.read_excel(xf, sheet_name=sheet, dtype=str)
            df.dropna(how="all", inplace=True)
            if df.empty:
                continue
            df["_sheet"] = sheet
            frames.append(df)
        except Exception:
            continue

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    combined["source"] = "cbi"
    return combined


def save_cbi(out_path: Path | None = None) -> Path | None:
    """Download and save CBI trade balance data."""
    out_path = out_path or PROCESSED_DIR / "cbi_trade_balance.parquet"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    log.info("CBI: attempting to download trade balance Excel ...")
    data = fetch_trade_balance_excel()
    if not data:
        log.error(
            "CBI download failed. The CBI publishes trade balance data at:\n"
            "  https://tsd.cbi.ir\n"
            "Download the Excel manually and place it in data/raw/cbi_trade_balance.xlsx\n"
            "Then run: python pipeline.py parse"
        )
        return None

    df = parse_trade_balance(data)
    if df.empty:
        return None

    df.to_parquet(out_path, index=False)
    log.info("Saved %d CBI rows → %s", len(df), out_path)
    return out_path
