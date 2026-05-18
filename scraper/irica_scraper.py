"""
IRICA (گمرک ایران) Statistics Scraper
Downloads monthly/annual Excel files from irica.ir statistics section.

Known URL patterns (discovered from irica.ir structure):
  - Stats directory: /web_directory/55334-آمار.html
  - Annual subdirs:  /web_directory/NNNNN-*.html
  - File downloads:  /Portal/File/ShowFile.aspx?ID=...
                     /files/fa/news/.../*.xlsx
"""

import re
import time
import logging
import warnings
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# Suppress the urllib3 InsecureRequestWarning — we only skip TLS verification
# as a last-resort fallback for irica.ir's broken SSL, and we log it ourselves.
from urllib3.exceptions import InsecureRequestWarning
warnings.filterwarnings("ignore", category=InsecureRequestWarning)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

BASE_URL  = "https://www.irica.ir"
BASE_URL2 = "https://irica.ir"

STATS_URLS = [
    "https://www.irica.ir/web_directory/55334-%D8%A2%D9%85%D8%A7%D8%B1.html",
    "https://irica.ir/web_directory/55334-%D8%A2%D9%85%D8%A7%D8%B1.html",
]

# Known stat-directory IDs on irica.ir.
# 55336 returns 404 for all known slugs so it is excluded.
KNOWN_STAT_DIRS = [
    55334,  # آمار (root)
    55335,  # آمار سال جاری
    55337,  # آمار صادرات
    55338,  # آمار واردات
    55339,  # آمار ترانزیت
]

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def fetch(url: str, timeout: int = 30, retries: int = 4) -> requests.Response | None:
    delay = 2
    for attempt in range(retries):
        # Only disable TLS verification on the very last retry (and only when
        # there was at least one prior attempt with verify=True) so that the
        # InsecureRequestWarning is never triggered on single-shot probes.
        is_last = attempt == retries - 1
        verify = not (is_last and retries > 1)
        if not verify:
            log.debug("Retrying %s without TLS verification", url)
        try:
            resp = SESSION.get(url, timeout=timeout, allow_redirects=True, verify=verify)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            log.warning("Attempt %d/%d failed for %s: %s", attempt + 1, retries, url, e)
            if attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
    log.error("All retries exhausted for %s", url)
    return None


def _try_base(path: str) -> str | None:
    """Try both www and non-www base URLs, return the one that works."""
    for base in (BASE_URL, BASE_URL2):
        resp = fetch(urljoin(base, path), timeout=10, retries=1)
        if resp:
            return urljoin(base, path)
    return None


_SLUG_CANDIDATES = [
    "%D8%A2%D9%85%D8%A7%D8%B1",                          # آمار
    "%D8%A2%D9%85%D8%A7%D8%B1-%D8%B3%D8%A7%D9%84-%D8%AC%D8%A7%D8%B1%DB%8C",  # آمار-سال-جاری
    "%D8%A2%D9%85%D8%A7%D8%B1%D9%87%D8%A7%DB%8C-%D8%B3%D8%A7%D9%84%DB%8C%D8%A7%D9%86%D9%87",  # آمارهای-سالیانه
    "%D8%A2%D9%85%D8%A7%D8%B1-%D8%B5%D8%A7%D8%AF%D8%B1%D8%A7%D8%AA",  # آمار-صادرات
    "%D8%A2%D9%85%D8%A7%D8%B1-%D9%88%D8%A7%D8%B1%D8%AF%D8%A7%D8%AA",  # آمار-واردات
    "%D8%A2%D9%85%D8%A7%D8%B1-%D8%AA%D8%B1%D8%A7%D9%86%D8%B2%DB%8C%D8%AA",  # آمار-ترانزیت
]


def discover_stat_pages(base: str) -> list[str]:
    """Crawl the stats directory and return all sub-page URLs."""
    pages: set[str] = set()

    # Try known directory IDs with multiple possible slug suffixes
    for dir_id in KNOWN_STAT_DIRS:
        for slug in _SLUG_CANDIDATES:
            url = f"{base}/web_directory/{dir_id}-{slug}.html"
            resp = fetch(url, timeout=10, retries=1)
            if resp:
                soup = BeautifulSoup(resp.text, "lxml")
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if re.search(r"/web_directory/\d+", href):
                        pages.add(urljoin(base, href))
                break  # found a working slug for this ID

    # Also crawl the main stats page
    for stats_url in STATS_URLS:
        resp = fetch(stats_url, timeout=15, retries=2)
        if not resp:
            continue
        soup = BeautifulSoup(resp.text, "lxml")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if re.search(r"/web_directory/\d+", href):
                pages.add(urljoin(base, href))
        break

    log.info("Discovered %d stat sub-pages", len(pages))
    return sorted(pages)


def _extract_links_from_soup(soup: BeautifulSoup, page_url: str) -> list[dict]:
    """Pull every plausible Excel / file-download link out of a parsed page."""
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        is_excel   = re.search(r"\.(xlsx?|xls)(\?.*)?$", href, re.IGNORECASE)
        is_portal  = re.search(r"ShowFile\.aspx|FileDownload|DownloadFile|GetFile", href, re.IGNORECASE)
        is_dl_kw   = re.search(r"download|دانلود|فایل", href, re.IGNORECASE)
        is_dl_kw  |= re.search(r"download|دانلود|فایل", a.get_text(), re.IGNORECASE)
        if is_excel or is_portal or is_dl_kw:
            full_url = urljoin(page_url, href) if not href.startswith("http") else href
            label = a.get_text(strip=True) or Path(urlparse(href).path).stem
            links.append({"url": full_url, "label": label, "source_page": page_url})
    return links


def find_excel_links(page_url: str, follow_subpages: bool = True) -> list[dict]:
    """
    Extract all Excel download links from a page.
    If the page itself has no file links but has sub-page links, follow those
    one level deeper (category index pages on irica.ir commonly work this way).
    """
    resp = fetch(page_url)
    if not resp:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    links = _extract_links_from_soup(soup, page_url)

    if links or not follow_subpages:
        return links

    # No direct file links — check if there are sub-directory links to follow
    sub_urls: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if re.search(r"/web_directory/\d+", href):
            sub_urls.append(urljoin(page_url, href) if not href.startswith("http") else href)

    for sub_url in sub_urls[:20]:  # cap to avoid runaway crawling
        sub_resp = fetch(sub_url, timeout=20, retries=2)
        if not sub_resp:
            continue
        sub_soup = BeautifulSoup(sub_resp.text, "lxml")
        links.extend(_extract_links_from_soup(sub_soup, sub_url))
        time.sleep(0.3)

    return links


def probe_content_type(url: str) -> bool:
    """HEAD request to verify URL points to an Excel file."""
    try:
        r = SESSION.head(url, timeout=10, allow_redirects=True)
        ct = r.headers.get("content-type", "")
        return any(t in ct for t in ("excel", "spreadsheet", "octet-stream", "zip"))
    except Exception:
        return True  # optimistic


def download_file(url: str, dest: Path) -> bool:
    if dest.exists():
        log.info("Already downloaded: %s", dest.name)
        return True

    log.info("Downloading: %s", url)
    resp = fetch(url, timeout=90)
    if not resp:
        return False
    if len(resp.content) < 512:
        log.warning("Suspiciously small file (%d bytes), skipping", len(resp.content))
        return False

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(resp.content)
    log.info("Saved: %s (%.0f KB)", dest.name, len(resp.content) / 1024)
    return True


def safe_filename(label: str, url: str) -> str:
    url_part = Path(urlparse(url).path).stem[:40]
    clean = re.sub(r"[^\w؀-ۿ\-]", "_", label)[:50]
    ext_match = re.search(r"\.(xlsx?)(\?|$)", url, re.IGNORECASE)
    ext = ext_match.group(1).lower() if ext_match else "xlsx"
    return f"{clean}__{url_part}.{ext}"


def scrape(download: bool = True) -> list[dict]:
    """
    Main entry: discover & download all Excel trade data files from irica.ir.
    Returns list of file metadata dicts.
    """
    all_links: list[dict] = []
    working_base = None

    # Probe which base URL is reachable
    for base in (BASE_URL, BASE_URL2):
        r = fetch(base, timeout=12, retries=1)
        if r:
            working_base = base
            log.info("Reachable base: %s", base)
            break

    if not working_base:
        log.error(
            "Cannot reach irica.ir — run this scraper from your local machine "
            "where the site is accessible."
        )
        return []

    # Direct scan of stats pages
    for stats_url in STATS_URLS:
        direct = find_excel_links(stats_url, follow_subpages=False)
        all_links.extend(direct)
        if direct:
            log.info("Direct links from %s: %d", stats_url, len(direct))
            break

    # Deep crawl sub-pages (each call follows one extra hop if needed)
    sub_pages = discover_stat_pages(working_base)
    for page in sub_pages:
        links = find_excel_links(page, follow_subpages=True)
        all_links.extend(links)
        time.sleep(0.5)

    # Deduplicate by URL
    seen: set[str] = set()
    unique = []
    for item in all_links:
        if item["url"] not in seen:
            seen.add(item["url"])
            unique.append(item)
    all_links = unique

    log.info("Total unique Excel links: %d", len(all_links))

    if download:
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        for item in all_links:
            fname = safe_filename(item["label"], item["url"])
            dest = RAW_DIR / fname
            ok = download_file(item["url"], dest)
            item["local_path"] = str(dest) if ok else None
            item["downloaded"] = ok
            time.sleep(0.4)

    return all_links


# ── Manual import helper ─────────────────────────────────────────────────────

def register_manual(file_path: str, year: int, direction: str) -> dict:
    """
    Register a manually downloaded Excel file.
    Usage: python -c "from scraper.irica_scraper import register_manual; register_manual('~/Downloads/export_1402.xlsx', 1402, 'export')"
    """
    src = Path(file_path).expanduser().resolve()
    if not src.exists():
        raise FileNotFoundError(src)
    dest = RAW_DIR / f"{direction}_{year}__{src.name}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.copy2(src, dest)
    log.info("Registered: %s → %s", src.name, dest)
    return {"local_path": str(dest), "year": year, "direction": direction}


if __name__ == "__main__":
    results = scrape(download=True)
    if results:
        print(f"\n{'='*60}")
        print(f"Found {len(results)} files")
        for r in results:
            status = "✓" if r.get("downloaded") else "✗"
            print(f"  [{status}] {r.get('label', '')} → {r['url'][:70]}")
    else:
        print("\nNo files found. Try running from a machine with access to irica.ir")
        print("Or place Excel files manually in data/raw/ and run: python pipeline.py parse")
