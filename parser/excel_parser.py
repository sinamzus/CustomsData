"""
IRICA Excel File Parser
Reads monthly/annual trade Excel files from gمرک and normalizes them
into a unified schema suitable for database loading.
"""

import re
import hashlib
import logging
from pathlib import Path
from typing import Iterator

import pandas as pd

log = logging.getLogger(__name__)

# -----------------------------------------------------------------------
# Known column name mappings (Persian labels → canonical English names)
# Files from different years use slightly different headers.
# -----------------------------------------------------------------------
COLUMN_MAP = {
    # Commodity
    "کد تعرفه": "hs_code",
    "کدتعرفه": "hs_code",
    "کد_تعرفه": "hs_code",
    "تعرفه": "hs_code",
    "كد تعرفه": "hs_code",
    "hs": "hs_code",
    "hs code": "hs_code",
    "شرح کالا": "commodity_description",
    "شرح كالا": "commodity_description",
    "نام کالا": "commodity_description",
    "description": "commodity_description",
    # Country
    "کشور": "country_name",
    "كشور": "country_name",
    "کشور مبدا": "country_name",
    "کشور مقصد": "country_name",
    "كشور مبدا": "country_name",
    "كشور مقصد": "country_name",
    "country": "country_name",
    # Customs office
    "گمرک": "customs_office",
    "گمرك": "customs_office",
    "نام گمرک": "customs_office",
    "گمرکات": "customs_office",
    # Weight
    "وزن خالص": "net_weight_kg",
    "وزن ناخالص": "gross_weight_kg",
    "وزن": "net_weight_kg",
    "net weight": "net_weight_kg",
    "gross weight": "gross_weight_kg",
    # Value
    "ارزش ریالی": "value_rial",
    "ارزش دلاری": "value_usd",
    "ارزش": "value_usd",
    "ارزش(دلار)": "value_usd",
    "ارزش (دلار)": "value_usd",
    "ارزش cif": "value_cif_usd",
    "ارزش fob": "value_fob_usd",
    "value": "value_usd",
    # Quantity
    "تعداد": "quantity",
    "مقدار": "quantity",
    "آمار": "quantity",
    # Date/period
    "ماه": "month",
    "سال": "year",
    "دوره": "period",
    # Province
    "استان": "province",
}

KNOWN_DIRECTIONS = {
    "صادرات": "export",
    "واردات": "import",
    "ترانزيت": "transit",
    "ترانزیت": "transit",
}


def _normalize_header(col: str) -> str:
    """Strip whitespace/ZWNJ, lowercase, map to canonical name."""
    col = str(col).strip().replace("‌", "").replace("\xa0", " ")
    col = re.sub(r"\s+", " ", col)
    lower = col.lower()
    return COLUMN_MAP.get(col, COLUMN_MAP.get(lower, col))


def _infer_direction(path: Path) -> str | None:
    """Guess export/import/transit from filename."""
    name = path.stem.lower()
    for fa, en in KNOWN_DIRECTIONS.items():
        if fa in name or en in name:
            return en
    return None


def _infer_year_month(path: Path) -> tuple[int | None, int | None]:
    """Extract Shamsi year and month from filename."""
    name = path.stem
    # Look for 4-digit year (13xx)
    year_match = re.search(r"1[34]\d{2}", name)
    year = int(year_match.group()) if year_match else None
    # Look for 1-2 digit month
    month_match = re.search(r"[\-_](\d{1,2})[\-_.]", name)
    month = int(month_match.group(1)) if month_match else None
    return year, month


def _clean_hs_code(val) -> str | None:
    if pd.isna(val):
        return None
    s = re.sub(r"[^\d]", "", str(val))
    return s if s else None


def _to_numeric(series: pd.Series) -> pd.Series:
    """Convert Persian/Arabic digit strings to numeric."""
    persian_map = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    cleaned = series.astype(str).str.translate(persian_map)
    cleaned = cleaned.str.replace(",", "").str.replace(" ", "").str.strip()
    return pd.to_numeric(cleaned, errors="coerce")


def parse_file(path: Path) -> pd.DataFrame | None:
    """
    Parse a single IRICA Excel file.
    Returns a normalized DataFrame or None on failure.
    """
    path = Path(path)
    log.info("Parsing: %s", path.name)

    try:
        # Try reading — some files have a header offset
        for skip in (0, 1, 2, 3, 4):
            try:
                df = pd.read_excel(path, skiprows=skip, dtype=str, engine="openpyxl")
            except Exception:
                try:
                    df = pd.read_excel(path, skiprows=skip, dtype=str, engine="xlrd")
                except Exception:
                    continue

            # Drop completely empty rows/columns
            df.dropna(how="all", inplace=True)
            df.dropna(axis=1, how="all", inplace=True)

            if df.empty or len(df.columns) < 3:
                continue

            # Normalize column names
            df.columns = [_normalize_header(c) for c in df.columns]

            # Accept if we have at least one key column
            if any(c in df.columns for c in ("hs_code", "country_name", "value_usd", "net_weight_kg")):
                break
        else:
            log.warning("Could not find usable header in %s", path.name)
            return None

    except Exception as e:
        log.error("Failed to read %s: %s", path.name, e)
        return None

    # Add metadata columns from filename
    direction = _infer_direction(path)
    year, month = _infer_year_month(path)

    if "direction" not in df.columns and direction:
        df["direction"] = direction
    if "year" not in df.columns and year:
        df["year"] = year
    if "month" not in df.columns and month:
        df["month"] = month

    # Clean HS codes
    if "hs_code" in df.columns:
        df["hs_code"] = df["hs_code"].apply(_clean_hs_code)

    # Convert numeric columns
    for col in ("net_weight_kg", "gross_weight_kg", "value_usd", "value_rial",
                "value_cif_usd", "value_fob_usd", "quantity"):
        if col in df.columns:
            df[col] = _to_numeric(df[col])

    # Add source file hash for dedup
    df["source_file"] = path.name
    df["file_hash"] = hashlib.md5(path.read_bytes()).hexdigest()[:8]

    log.info("  → %d rows, columns: %s", len(df), list(df.columns))
    return df


def parse_directory(raw_dir: Path) -> pd.DataFrame:
    """Parse all Excel files in a directory and concatenate results."""
    raw_dir = Path(raw_dir)
    files = list(raw_dir.glob("*.xlsx")) + list(raw_dir.glob("*.xls"))
    log.info("Found %d Excel files in %s", len(files), raw_dir)

    frames: list[pd.DataFrame] = []
    for f in sorted(files):
        df = parse_file(f)
        if df is not None and not df.empty:
            frames.append(df)

    if not frames:
        log.warning("No data parsed from %s", raw_dir)
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    log.info("Total rows after combining: %d", len(combined))
    return combined


def iter_files(raw_dir: Path) -> Iterator[tuple[Path, pd.DataFrame]]:
    """Yield (path, dataframe) for each successfully parsed file."""
    raw_dir = Path(raw_dir)
    for f in sorted(raw_dir.glob("*.xls*")):
        df = parse_file(f)
        if df is not None and not df.empty:
            yield f, df


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    raw = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/raw")
    df = parse_directory(raw)

    if not df.empty:
        out = Path("data/processed/combined_trade.parquet")
        out.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(out, index=False)
        print(f"\nSaved {len(df):,} rows to {out}")
        print("\nColumn summary:")
        print(df.dtypes)
        print("\nSample:")
        print(df.head(3).to_string())
