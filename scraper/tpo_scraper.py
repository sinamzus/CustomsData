"""
TPO (Trade Promotion Organization of Iran / سازمان توسعه تجارت) scraper.

TPO publishes non-oil export statistics on its website (tpo.ir).
This module scrapes the public statistics section for Excel downloads.

TPO data complements IRICA by focusing on:
  - Non-oil export targets vs. actuals
  - Export by province and destination market
  - Trade facilitation statistics
"""

import re
import time
import logging
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

TPO_BASE      = "https://www.tpo.ir"
TPO_STAT_URLS = [
    "https://www.tpo.ir/fa/page/1905/آمار-صادرات-غیرنفتی",
    "https://www.tpo.ir/fa/page/1906",
    "https://www.tpo.ir/fa/staticpage/1905",
]

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
RAW_DIR       = Path(__file__).parent.parent / "data" / "raw"

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
    "Referer": TPO_BASE,
})


def _fetch(url: str, retries: int = 3) -> requests.Response | None:
    delay = 3
    for attempt in range(retries):
        try:
            r = SESSION.get(url, timeout=20, verify=False, allow_redirects=True)
            r.raise_for_status()
            return r
        except Exception as e:
            log.warning("TPO attempt %d/%d failed for %s: %s", attempt + 1, retries, url, e)
            if attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
    return None


def _find_excel_links(soup: BeautifulSoup, base_url: str) -> list[dict]:
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if re.search(r"\.(xlsx?|xls)(\?.*)?$", href, re.IGNORECASE):
            full = urljoin(base_url, href) if not href.startswith("http") else href
            links.append({"url": full, "label": a.get_text(strip=True), "source": "tpo"})
    return links


def scrape_tpo() -> list[dict]:
    """
    Crawl TPO statistics pages and return list of Excel file metadata.
    """
    all_links: list[dict] = []

    for stat_url in TPO_STAT_URLS:
        resp = _fetch(stat_url)
        if not resp:
            continue

        soup = BeautifulSoup(resp.text, "lxml")
        links = _find_excel_links(soup, stat_url)
        if links:
            log.info("TPO: found %d files at %s", len(links), stat_url)
            all_links.extend(links)
            break

        # Also look one level deeper via sub-links
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "آمار" in href or "stat" in href.lower() or "export" in href.lower():
                sub_url = urljoin(stat_url, href) if not href.startswith("http") else href
                sub_resp = _fetch(sub_url)
                if sub_resp:
                    sub_soup = BeautifulSoup(sub_resp.text, "lxml")
                    sub_links = _find_excel_links(sub_soup, sub_url)
                    all_links.extend(sub_links)
                time.sleep(0.5)

    # Deduplicate
    seen: set[str] = set()
    unique = [x for x in all_links if not (x["url"] in seen or seen.add(x["url"]))]
    log.info("TPO: %d unique Excel links found", len(unique))
    return unique


def download_tpo(out_dir: Path | None = None) -> list[dict]:
    """Download all TPO Excel files into data/raw/."""
    out_dir = out_dir or RAW_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    links = scrape_tpo()
    if not links:
        log.warning(
            "TPO: no files found automatically.\n"
            "You can download TPO statistics manually from https://www.tpo.ir\n"
            "and place them in data/raw/ then run: python pipeline.py parse"
        )
        return []

    for item in links:
        stem = Path(urlparse(item["url"]).path).stem[:60]
        dest = out_dir / f"tpo__{stem}.xlsx"
        if dest.exists():
            log.info("Already downloaded: %s", dest.name)
            item["local_path"] = str(dest)
            continue
        resp = _fetch(item["url"])
        if resp and len(resp.content) > 512:
            dest.write_bytes(resp.content)
            log.info("Saved: %s (%.0f KB)", dest.name, len(resp.content) / 1024)
            item["local_path"] = str(dest)
        time.sleep(0.5)

    return links
