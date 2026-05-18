"""
Iran Trade Map — Main ETL Pipeline

Usage:
  python pipeline.py scrape          # Download Excel files from irica.ir
  python pipeline.py parse           # Parse downloaded files → Parquet
  python pipeline.py normalize       # Normalize country/HS codes
  python pipeline.py load --db URL   # Load to PostgreSQL
  python pipeline.py run --db URL    # Full pipeline (scrape+parse+normalize+load)
  python pipeline.py report          # Quality report on processed data
"""

import sys
import json
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

RAW_DIR       = Path("data/raw")
PROCESSED_DIR = Path("data/processed")

COMBINED_PARQUET    = PROCESSED_DIR / "combined_trade.parquet"
NORMALIZED_PARQUET  = PROCESSED_DIR / "normalized_trade.parquet"


def cmd_scrape(args):
    from scraper.irica_scraper import scrape
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    results = scrape(download=True)
    log.info("Scrape complete — %d files found", len(results))
    # Save manifest
    manifest = PROCESSED_DIR / "scrape_manifest.json"
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    log.info("Manifest saved to %s", manifest)


def cmd_parse(args):
    import pandas as pd
    from parser.excel_parser import parse_directory

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df = parse_directory(RAW_DIR)

    if df.empty:
        log.error("No data parsed — check data/raw/ for Excel files")
        sys.exit(1)

    df.to_parquet(COMBINED_PARQUET, index=False)
    log.info("Saved %d rows to %s", len(df), COMBINED_PARQUET)


def cmd_normalize(args):
    import pandas as pd
    from utils.normalizer import run_all, quality_report

    if not COMBINED_PARQUET.exists():
        log.error("Run 'parse' first: %s not found", COMBINED_PARQUET)
        sys.exit(1)

    df = pd.read_parquet(COMBINED_PARQUET)
    log.info("Loaded %d rows for normalization", len(df))

    df = run_all(df)
    df.to_parquet(NORMALIZED_PARQUET, index=False)
    log.info("Normalized data saved to %s", NORMALIZED_PARQUET)

    report = quality_report(df)
    log.info("Quality report:\n%s", json.dumps(report, ensure_ascii=False, indent=2))


def cmd_load(args):
    import pandas as pd
    from db.loader import get_engine, init_schema, seed_reference_tables, load_dataframe

    db_url = getattr(args, "db", None)
    if not db_url:
        log.error("Provide --db postgresql://user:pass@host/dbname")
        sys.exit(1)

    if not NORMALIZED_PARQUET.exists():
        log.error("Run 'normalize' first")
        sys.exit(1)

    df = pd.read_parquet(NORMALIZED_PARQUET)
    engine = get_engine(db_url)
    init_schema(engine)
    seed_reference_tables(engine)
    n = load_dataframe(df, engine)
    log.info("Loaded %d rows into database", n)


def cmd_run(args):
    cmd_scrape(args)
    cmd_parse(args)
    cmd_normalize(args)
    if getattr(args, "db", None):
        cmd_load(args)


def cmd_report(args):
    import pandas as pd
    from utils.normalizer import quality_report

    path = NORMALIZED_PARQUET if NORMALIZED_PARQUET.exists() else COMBINED_PARQUET
    if not path.exists():
        log.error("No processed data found — run parse/normalize first")
        sys.exit(1)

    df = pd.read_parquet(path)
    report = quality_report(df)
    print(json.dumps(report, ensure_ascii=False, indent=2))


COMMANDS = {
    "scrape":    cmd_scrape,
    "parse":     cmd_parse,
    "normalize": cmd_normalize,
    "load":      cmd_load,
    "run":       cmd_run,
    "report":    cmd_report,
}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Iran Trade Map ETL Pipeline")
    parser.add_argument("command", choices=COMMANDS.keys())
    parser.add_argument("--db", help="PostgreSQL connection URL", default=None)
    parsed = parser.parse_args()

    COMMANDS[parsed.command](parsed)
