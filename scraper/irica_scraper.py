"""
IRICA (گمرک ایران) Statistics Scraper
Downloads monthly Excel files from irica.ir statistics section.
"""

import os
import re
import time
import logging
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

BASE_URL = "https://www.irica.ir"
STATS_URL = "https://www.irica.ir/web_directory/55334-%D8%A2%D9%85%D8%A7%D8%B1.html"

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": BASE_URL,
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def fetch(url: str, timeout: int = 30, retries: int = 4) -> requests.Response | None:
    delay = 2
    for attempt in range(retries):
        try:
            resp = SESSION.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            log.warning("Attempt %d/%d failed for %s: %s", attempt + 1, retries, url, e)
            if attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
    log.error("All retries exhausted for %s", url)
    return None


def discover_stat_pages() -> list[str]:
    """Find all sub-pages under the statistics directory."""
    log.info("Fetching stats index: %s", STATS_URL)
    resp = fetch(STATS_URL)
    if not resp:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    pages = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # IRICA stat pages follow pattern /web_directory/NNNNN-*.html
        if re.search(r"/web_directory/\d+", href):
            full = urljoin(BASE_URL, href)
            if full not in pages:
                pages.append(full)

    log.info("Discovered %d stat sub-pages", len(pages))
    return pages


def find_excel_links(page_url: str) -> list[dict]:
    """Extract all Excel download links from a statistics page."""
    resp = fetch(page_url)
    if not resp:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    links = []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if re.search(r"\.(xlsx?|xls)(\?.*)?$", href, re.IGNORECASE):
            full_url = urljoin(BASE_URL, href) if not href.startswith("http") else href
            label = a.get_text(strip=True) or Path(urlparse(href).path).name
            links.append({"url": full_url, "label": label, "source_page": page_url})

    return links


def download_file(url: str, dest: Path) -> bool:
    if dest.exists():
        log.info("Already downloaded: %s", dest.name)
        return True

    log.info("Downloading: %s", url)
    resp = fetch(url, timeout=60)
    if not resp:
        return False

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(resp.content)
    log.info("Saved: %s (%.1f KB)", dest.name, len(resp.content) / 1024)
    return True


def safe_filename(label: str, url: str) -> str:
    """Generate a clean filename from label + url."""
    url_part = Path(urlparse(url).path).stem
    clean = re.sub(r'[^\w؀-ۿ\-]', '_', label)[:60]
    ext_match = re.search(r"\.(xlsx?)(\?|$)", url, re.IGNORECASE)
    ext = ext_match.group(1).lower() if ext_match else "xlsx"
    return f"{clean}__{url_part}.{ext}"


def scrape(download: bool = True) -> list[dict]:
    """
    Main entry point.
    Returns list of found file metadata.
    If download=True, saves files to data/raw/.
    """
    all_links: list[dict] = []

    # Try main stats page directly first
    direct = find_excel_links(STATS_URL)
    all_links.extend(direct)
    log.info("Direct links from stats page: %d", len(direct))

    # Then crawl sub-pages
    sub_pages = discover_stat_pages()
    for page in sub_pages:
        if page == STATS_URL:
            continue
        links = find_excel_links(page)
        all_links.extend(links)
        time.sleep(0.5)  # polite crawling

    log.info("Total Excel links found: %d", len(all_links))

    if download:
        for item in all_links:
            fname = safe_filename(item["label"], item["url"])
            dest = RAW_DIR / fname
            download_file(item["url"], dest)
            item["local_path"] = str(dest)
            time.sleep(0.3)

    return all_links


if __name__ == "__main__":
    results = scrape(download=True)
    print(f"\n{'='*60}")
    print(f"Found {len(results)} files")
    for r in results:
        print(f"  [{r.get('label', '')}] {r['url']}")
