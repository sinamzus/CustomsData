"""
Iran Trade Map — Main ETL Pipeline

Commands:
  python pipeline.py scrape          # Download Excel files from irica.ir → data/raw/
  python pipeline.py parse           # Parse downloaded files → data/processed/combined_trade.parquet
  python pipeline.py normalize       # Normalize country/HS codes + quality report
  python pipeline.py load --db URL   # Load into PostgreSQL
  python pipeline.py run --db URL    # Full pipeline: scrape → parse → normalize → (load)
  python pipeline.py demo            # Generate sample data and start API (no real data needed)
  python pipeline.py report          # Quality report on current processed data
  python pipeline.py check           # Connectivity check: can we reach irica.ir?
"""

import sys
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

RAW_DIR            = Path("data/raw")
PROCESSED_DIR      = Path("data/processed")
COMBINED_PARQUET   = PROCESSED_DIR / "combined_trade.parquet"
NORMALIZED_PARQUET = PROCESSED_DIR / "normalized_trade.parquet"
SAMPLE_PARQUET     = PROCESSED_DIR / "sample_trade.parquet"


# ── helpers ──────────────────────────────────────────────────────────────────

def _require_normalized():
    if not NORMALIZED_PARQUET.exists():
        log.error("Run 'normalize' first (or 'demo' for sample data)")
        sys.exit(1)


def _require_combined():
    if not COMBINED_PARQUET.exists():
        log.error("Run 'parse' first. If you have no Excel files yet, run 'scrape' or 'demo'.")
        sys.exit(1)


# ── commands ─────────────────────────────────────────────────────────────────

def cmd_check(args):
    """Verify connectivity to irica.ir before scraping."""
    from scraper.irica_scraper import fetch, BASE_URL, BASE_URL2
    print("Checking connectivity to irica.ir ...")
    ok = False
    for url in (BASE_URL, BASE_URL2, "https://irica.gov.ir"):
        resp = fetch(url, timeout=12, retries=1)
        status = f"✓ OK ({resp.status_code})" if resp else "✗ FAILED"
        print(f"  {url:45s}  {status}")
        if resp:
            ok = True
    print()
    if ok:
        print("Connection OK — you can run:  python pipeline.py scrape")
    else:
        print("Cannot reach irica.ir from this machine.")
        print("Make sure you are on a network with access to Iranian websites.")
        sys.exit(1)


def cmd_scrape(args):
    """Download all available Excel files from irica.ir into data/raw/."""
    from scraper.irica_scraper import scrape
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    results = scrape(download=True)
    if not results:
        log.error(
            "No files found. Run 'python pipeline.py check' to diagnose connectivity."
        )
        sys.exit(1)
    manifest = PROCESSED_DIR / "scrape_manifest.json"
    manifest.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    downloaded = sum(1 for r in results if r.get("downloaded"))
    log.info("Scrape complete — %d files found, %d downloaded → manifest: %s",
             len(results), downloaded, manifest)


def cmd_parse(args):
    """Parse all Excel files in data/raw/ → data/processed/combined_trade.parquet."""
    import pandas as pd
    from parser.excel_parser import parse_directory

    raw_files = list(RAW_DIR.glob("*.xlsx")) + list(RAW_DIR.glob("*.xls"))
    if not raw_files:
        log.error(
            "No Excel files in data/raw/\n"
            "  Option 1: Run 'python pipeline.py scrape' (needs Iran network)\n"
            "  Option 2: Copy Excel files manually to data/raw/\n"
            "  Option 3: Run 'python pipeline.py demo' to use synthetic data"
        )
        sys.exit(1)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df = parse_directory(RAW_DIR)
    if df.empty:
        log.error("Parsing produced 0 rows — check that files are valid IRICA Excel exports")
        sys.exit(1)

    df.to_parquet(COMBINED_PARQUET, index=False)
    log.info("Saved %d rows → %s", len(df), COMBINED_PARQUET)


def cmd_normalize(args):
    """Normalize country names → ISO3, enrich HS codes, run quality report."""
    import pandas as pd
    from utils.normalizer import run_all, quality_report

    _require_combined()
    df = pd.read_parquet(COMBINED_PARQUET)
    log.info("Loaded %d rows for normalization", len(df))

    df = run_all(df)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(NORMALIZED_PARQUET, index=False)
    log.info("Normalized data saved → %s", NORMALIZED_PARQUET)

    report = quality_report(df)
    print("\n── Quality Report ──────────────────────────────────")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def cmd_load(args):
    """Load normalized Parquet into PostgreSQL."""
    import pandas as pd
    from db.loader import get_engine, init_schema, seed_reference_tables, load_dataframe

    db_url = getattr(args, "db", None)
    if not db_url:
        log.error("Provide --db postgresql://user:pass@host/dbname")
        sys.exit(1)
    _require_normalized()

    df = pd.read_parquet(NORMALIZED_PARQUET)
    engine = get_engine(db_url)
    init_schema(engine)
    seed_reference_tables(engine)
    n = load_dataframe(df, engine)
    log.info("Loaded %d rows into PostgreSQL", n)


def cmd_run(args):
    """Full pipeline: scrape → parse → normalize → (load if --db given)."""
    cmd_scrape(args)
    cmd_parse(args)
    cmd_normalize(args)
    if getattr(args, "db", None):
        cmd_load(args)


def cmd_demo(args):
    """Generate synthetic sample data (1379–1403) and start the API server."""
    import subprocess
    from utils.sample_data import save_sample

    if not SAMPLE_PARQUET.exists():
        log.info("Generating synthetic trade data (1379–1403) ...")
        save_sample(SAMPLE_PARQUET)
    else:
        log.info("Sample data already exists: %s", SAMPLE_PARQUET)

    print("\n" + "="*55)
    print(" Iran Trade Map — Demo Mode")
    print("="*55)
    print(f" Data:   {SAMPLE_PARQUET} (synthetic)")
    print(" API:    http://localhost:8000")
    print(" Docs:   http://localhost:8000/docs")
    print(" Map:    http://localhost:8000/")
    print("="*55 + "\n")

    subprocess.run(
        ["uvicorn", "api.main:app", "--reload", "--port", "8000"],
        check=True,
    )


def cmd_report(args):
    """Show data quality metrics for the current processed dataset."""
    import pandas as pd
    from utils.normalizer import quality_report

    path = (NORMALIZED_PARQUET if NORMALIZED_PARQUET.exists()
            else COMBINED_PARQUET if COMBINED_PARQUET.exists()
            else SAMPLE_PARQUET)

    if not path.exists():
        log.error(
            "No data found. Run one of:\n"
            "  python pipeline.py run     (real data from irica.ir)\n"
            "  python pipeline.py demo    (synthetic sample data)"
        )
        sys.exit(1)

    df = pd.read_parquet(path)
    report = quality_report(df)
    print(f"Source: {path}")
    print(json.dumps(report, ensure_ascii=False, indent=2))


# ── CLI ───────────────────────────────────────────────────────────────────────

COMMANDS = {
    "check":     cmd_check,
    "scrape":    cmd_scrape,
    "parse":     cmd_parse,
    "normalize": cmd_normalize,
    "load":      cmd_load,
    "run":       cmd_run,
    "demo":      cmd_demo,
    "report":    cmd_report,
}

if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(
        description="Iran Trade Map ETL Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("command", choices=COMMANDS.keys())
    p.add_argument("--db", help="PostgreSQL URL: postgresql://user:pass@host/dbname",
                   default=None)
    args = p.parse_args()
    COMMANDS[args.command](args)
