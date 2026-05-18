"""
Iran Trade Map — Main ETL Pipeline

Commands:
  python pipeline.py scrape              # Download Excel files from irica.ir → data/raw/
  python pipeline.py scrape-comtrade     # Fetch UN Comtrade bilateral trade data
  python pipeline.py scrape-worldbank    # Fetch World Bank macro indicators
  python pipeline.py scrape-cbi          # Fetch Central Bank of Iran trade balance
  python pipeline.py scrape-tpo          # Fetch TPO non-oil export statistics
  python pipeline.py scrape-all          # Fetch from ALL sources above
  python pipeline.py parse               # Parse downloaded Excel files → combined_trade.parquet
  python pipeline.py normalize           # Normalize country/HS codes + quality report
  python pipeline.py load --db URL       # Load into PostgreSQL
  python pipeline.py run --db URL        # Full pipeline: scrape-all → parse → normalize → (load)
  python pipeline.py demo                # Generate sample data and start API
  python pipeline.py report              # Quality report on current processed data
  python pipeline.py check               # Connectivity check

Data sources used:
  1. IRICA (گمرک ایران)        — irica.ir         — item-level HS6 trade records
  2. UN Comtrade                — comtrade.un.org   — bilateral trade by HS chapter/year
  3. World Bank                 — worldbank.org     — macro indicators (GDP, exports, imports)
  4. CBI (بانک مرکزی)          — tsd.cbi.ir        — trade balance / BOP
  5. TPO (سازمان توسعه تجارت)  — tpo.ir            — non-oil export statistics
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
COMTRADE_PARQUET   = PROCESSED_DIR / "comtrade_iran.parquet"
WORLDBANK_PARQUET  = PROCESSED_DIR / "worldbank_iran.parquet"
CBI_PARQUET        = PROCESSED_DIR / "cbi_trade_balance.parquet"


# ── helpers ───────────────────────────────────────────────────────────────────

def _require_normalized():
    if not NORMALIZED_PARQUET.exists():
        log.error("Run 'normalize' first (or 'demo' for sample data)")
        sys.exit(1)


def _require_combined():
    if not COMBINED_PARQUET.exists():
        log.error("Run 'parse' first. If you have no Excel files yet, run 'scrape-all' or 'demo'.")
        sys.exit(1)


# ── commands ──────────────────────────────────────────────────────────────────

def cmd_check(args):
    """Verify connectivity to key data sources."""
    from scraper.irica_scraper import fetch, BASE_URL, BASE_URL2
    checks = [
        (BASE_URL,                       "IRICA (گمرک)"),
        (BASE_URL2,                      "IRICA alt"),
        ("https://comtrade.un.org",      "UN Comtrade"),
        ("https://api.worldbank.org/v2", "World Bank API"),
        ("https://tsd.cbi.ir",           "CBI (بانک مرکزی)"),
        ("https://www.tpo.ir",           "TPO (توسعه تجارت)"),
    ]
    ok = False
    for url, label in checks:
        resp = fetch(url, timeout=12, retries=1)
        status = f"OK ({resp.status_code})" if resp else "FAILED"
        print(f"  {label:30s} {url:45s}  {status}")
        if resp:
            ok = True
    print()
    if ok:
        print("At least one source reachable. Run: python pipeline.py scrape-all")
    else:
        print("No sources reachable — check your network connection.")
        sys.exit(1)


def cmd_scrape(args):
    """Download Excel files from IRICA (گمرک) → data/raw/."""
    from scraper.irica_scraper import scrape
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    results = scrape(download=True)
    if not results:
        log.error("No IRICA files found. Run 'python pipeline.py check' to diagnose connectivity.")
        sys.exit(1)
    manifest = PROCESSED_DIR / "scrape_manifest.json"
    manifest.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    downloaded = sum(1 for r in results if r.get("downloaded"))
    log.info("IRICA scrape complete — %d files found, %d downloaded", len(results), downloaded)


def cmd_scrape_comtrade(args):
    """Fetch Iran bilateral trade data from UN Comtrade API."""
    from scraper.comtrade_scraper import save_comtrade
    years = list(range(2010, 2025))
    log.info("Fetching UN Comtrade data for years %d–%d ...", years[0], years[-1])
    path = save_comtrade(years, out_path=COMTRADE_PARQUET)
    log.info("Comtrade data saved → %s", path)


def cmd_scrape_worldbank(args):
    """Fetch World Bank macro trade indicators for Iran."""
    from scraper.worldbank_scraper import save_worldbank
    log.info("Fetching World Bank indicators for Iran (2000–2024) ...")
    path = save_worldbank(out_path=WORLDBANK_PARQUET, start=2000, end=2024)
    log.info("World Bank data saved → %s", path)


def cmd_scrape_cbi(args):
    """Fetch Central Bank of Iran trade balance data."""
    from scraper.cbi_scraper import save_cbi
    log.info("Fetching CBI (بانک مرکزی) trade balance ...")
    path = save_cbi(out_path=CBI_PARQUET)
    if path:
        log.info("CBI data saved → %s", path)
    else:
        log.warning(
            "CBI automated download failed.\n"
            "Download manually from https://tsd.cbi.ir and place in data/raw/cbi_trade_balance.xlsx"
        )


def cmd_scrape_tpo(args):
    """Fetch TPO (سازمان توسعه تجارت) non-oil export statistics."""
    from scraper.tpo_scraper import download_tpo
    log.info("Fetching TPO non-oil export data ...")
    results = download_tpo(out_dir=RAW_DIR)
    if results:
        log.info("TPO: %d files downloaded", len(results))
    else:
        log.warning(
            "TPO automated download found no files.\n"
            "Download manually from https://www.tpo.ir and place in data/raw/"
        )


def cmd_scrape_all(args):
    """Fetch from ALL data sources: IRICA, Comtrade, World Bank, CBI, TPO."""
    log.info("=" * 60)
    log.info("Scraping ALL Iran trade data sources")
    log.info("=" * 60)

    log.info("\n[1/5] IRICA (گمرک ایران) ...")
    try:
        cmd_scrape(args)
    except SystemExit:
        log.warning("IRICA scrape failed — continuing with other sources")

    log.info("\n[2/5] UN Comtrade ...")
    try:
        cmd_scrape_comtrade(args)
    except Exception as e:
        log.warning("Comtrade scrape failed: %s", e)

    log.info("\n[3/5] World Bank ...")
    try:
        cmd_scrape_worldbank(args)
    except Exception as e:
        log.warning("World Bank scrape failed: %s", e)

    log.info("\n[4/5] CBI (بانک مرکزی) ...")
    try:
        cmd_scrape_cbi(args)
    except Exception as e:
        log.warning("CBI scrape failed: %s", e)

    log.info("\n[5/5] TPO (سازمان توسعه تجارت) ...")
    try:
        cmd_scrape_tpo(args)
    except Exception as e:
        log.warning("TPO scrape failed: %s", e)

    log.info("\nAll sources attempted. Run: python pipeline.py parse")


def cmd_parse(args):
    """Parse all Excel files in data/raw/ → data/processed/combined_trade.parquet."""
    import pandas as pd
    from parser.excel_parser import parse_directory

    raw_files = list(RAW_DIR.glob("*.xlsx")) + list(RAW_DIR.glob("*.xls"))
    if not raw_files:
        log.error(
            "No Excel files in data/raw/\n"
            "  Option 1: Run 'python pipeline.py scrape-all'\n"
            "  Option 2: Copy Excel files manually to data/raw/\n"
            "  Option 3: Run 'python pipeline.py demo' for synthetic data"
        )
        sys.exit(1)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df = parse_directory(RAW_DIR)
    if df.empty:
        log.error("Parsing produced 0 rows — check that files are valid IRICA/TPO Excel exports")
        sys.exit(1)

    # Merge with Comtrade if available (different schema → store separately but note it)
    if COMTRADE_PARQUET.exists():
        ct = pd.read_parquet(COMTRADE_PARQUET)
        log.info("Comtrade data available: %d rows (kept separate in %s)", len(ct), COMTRADE_PARQUET)

    if WORLDBANK_PARQUET.exists():
        wb = pd.read_parquet(WORLDBANK_PARQUET)
        log.info("World Bank data available: %d rows (kept separate in %s)", len(wb), WORLDBANK_PARQUET)

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

    # Also report on auxiliary sources
    for label, path in [("UN Comtrade", COMTRADE_PARQUET), ("World Bank", WORLDBANK_PARQUET)]:
        if path.exists():
            aux = pd.read_parquet(path)
            print(f"\n── {label}: {len(aux)} rows, columns: {list(aux.columns)}")


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

    # Load auxiliary sources if available
    for label, path, table in [
        ("UN Comtrade", COMTRADE_PARQUET,  "comtrade_trade"),
        ("World Bank",  WORLDBANK_PARQUET, "worldbank_indicators"),
    ]:
        if path.exists():
            aux = pd.read_parquet(path)
            try:
                aux.to_sql(table, engine, if_exists="replace", index=False)
                log.info("Loaded %d %s rows → table '%s'", len(aux), label, table)
            except Exception as e:
                log.warning("Could not load %s into DB: %s", label, e)


def cmd_run(args):
    """Full pipeline: scrape-all → parse → normalize → (load if --db given)."""
    cmd_scrape_all(args)
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
    """Show data quality metrics and source inventory."""
    import pandas as pd
    from utils.normalizer import quality_report

    print("\n── Data Source Inventory ───────────────────────────")
    sources = [
        ("IRICA (normalized)",  NORMALIZED_PARQUET),
        ("IRICA (combined)",    COMBINED_PARQUET),
        ("IRICA (sample)",      SAMPLE_PARQUET),
        ("UN Comtrade",         COMTRADE_PARQUET),
        ("World Bank",          WORLDBANK_PARQUET),
        ("CBI trade balance",   CBI_PARQUET),
    ]
    any_found = False
    for label, path in sources:
        if path.exists():
            df = pd.read_parquet(path)
            print(f"  {label:25s} {len(df):>8,} rows   {path}")
            any_found = True
        else:
            print(f"  {label:25s} {'—':>8}         (not yet downloaded)")

    if not any_found:
        log.error(
            "No data found. Run one of:\n"
            "  python pipeline.py scrape-all  (all real data sources)\n"
            "  python pipeline.py demo         (synthetic sample data)"
        )
        sys.exit(1)

    # Quality report on best available IRICA data
    for path in (NORMALIZED_PARQUET, COMBINED_PARQUET, SAMPLE_PARQUET):
        if path.exists():
            df = pd.read_parquet(path)
            report = quality_report(df)
            print(f"\n── IRICA Quality Report ({path.name}) ──")
            print(json.dumps(report, ensure_ascii=False, indent=2))
            break


# ── CLI ───────────────────────────────────────────────────────────────────────

COMMANDS = {
    "check":           cmd_check,
    "scrape":          cmd_scrape,
    "scrape-comtrade": cmd_scrape_comtrade,
    "scrape-worldbank":cmd_scrape_worldbank,
    "scrape-cbi":      cmd_scrape_cbi,
    "scrape-tpo":      cmd_scrape_tpo,
    "scrape-all":      cmd_scrape_all,
    "parse":           cmd_parse,
    "normalize":       cmd_normalize,
    "load":            cmd_load,
    "run":             cmd_run,
    "demo":            cmd_demo,
    "report":          cmd_report,
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
