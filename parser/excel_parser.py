"""
IRICA Excel File Parser
Handles the various Excel formats published by Iran's customs authority.

IRICA publishes several file layouts depending on year and report type.
This parser auto-detects the layout and normalizes to a unified schema.
"""

import re
import hashlib
import logging
from pathlib import Path
from typing import Iterator

import pandas as pd

log = logging.getLogger(__name__)

# ── Column name normalizer ────────────────────────────────────────────────────
# Maps every known Persian/English header variant → canonical English name.
COLUMN_MAP = {
    # HS / tariff code
    "کد تعرفه": "hs_code", "کدتعرفه": "hs_code", "کد_تعرفه": "hs_code",
    "تعرفه": "hs_code", "كد تعرفه": "hs_code", "hs": "hs_code",
    "hs code": "hs_code", "hs_code": "hs_code", "tariff": "hs_code",
    "کد کالا": "hs_code",

    # Commodity description
    "شرح کالا": "commodity_description", "شرح كالا": "commodity_description",
    "نام کالا": "commodity_description", "نام كالا": "commodity_description",
    "description": "commodity_description", "شرح": "commodity_description",
    "commodity": "commodity_description",

    # Country
    "کشور": "country_name", "كشور": "country_name",
    "کشور مبدا": "country_name", "کشور مقصد": "country_name",
    "كشور مبدا": "country_name", "كشور مقصد": "country_name",
    "country": "country_name", "مبدا": "country_name", "مقصد": "country_name",

    # Customs office
    "گمرک": "customs_office", "گمرك": "customs_office",
    "نام گمرک": "customs_office", "گمرکات": "customs_office",
    "customs": "customs_office",

    # Province
    "استان": "province", "استان صادر كننده": "province",
    "استان صادرکننده": "province",

    # Net weight
    "وزن خالص": "net_weight_kg", "net weight": "net_weight_kg",
    "وزن خالص(كيلوگرم)": "net_weight_kg", "وزن خالص (کیلوگرم)": "net_weight_kg",
    "net_weight": "net_weight_kg",

    # Gross weight
    "وزن ناخالص": "gross_weight_kg", "gross weight": "gross_weight_kg",
    "وزن ناخالص(كيلوگرم)": "gross_weight_kg",

    # Generic weight (treat as net)
    "وزن": "net_weight_kg", "weight": "net_weight_kg",

    # Values
    "ارزش ریالی": "value_rial", "ارزش(ريال)": "value_rial",
    "ارزش (ریال)": "value_rial",
    "ارزش دلاری": "value_usd", "ارزش(دلار)": "value_usd",
    "ارزش (دلار)": "value_usd", "value": "value_usd",
    "ارزش": "value_usd",
    "ارزش cif": "value_cif_usd", "ارزش fob": "value_fob_usd",
    "cif value": "value_cif_usd", "fob value": "value_fob_usd",
    "ارزش گمركي": "value_cif_usd", "ارزش گمرکی": "value_cif_usd",

    # Quantity
    "تعداد": "quantity", "مقدار": "quantity",
    "آمار": "quantity", "quantity": "quantity",
    "تعداد/مقدار": "quantity",

    # Unit
    "واحد": "quantity_unit", "unit": "quantity_unit",

    # Date / period
    "ماه": "month", "month": "month",
    "سال": "year", "year": "year",
    "دوره": "period", "period": "period",

    # Direction
    "نوع معامله": "direction", "نوع": "direction",
    "direction": "direction",
}

DIRECTION_MAP = {
    "صادرات": "export", "export": "export", "exp": "export",
    "واردات": "import", "import": "import", "imp": "import",
    "ترانزیت": "transit", "ترانزيت": "transit", "transit": "transit",
}


def _normalize_col(col: str) -> str:
    """Clean a header cell and map to canonical column name."""
    col = str(col).strip()
    col = col.replace("‌", "").replace("\xa0", " ").replace("‌", "")
    col = re.sub(r"\s+", " ", col).strip()
    lower = col.lower()
    return COLUMN_MAP.get(col) or COLUMN_MAP.get(lower) or col


def _infer_direction_from_path(path: Path) -> str | None:
    name = path.stem.lower()
    for fa, en in DIRECTION_MAP.items():
        if fa in name or en in name[:8]:
            return en
    return None


def _infer_year_from_path(path: Path) -> int | None:
    name = path.stem
    m = re.search(r"1[34]\d{2}", name)
    return int(m.group()) if m else None


def _infer_month_from_path(path: Path) -> int | None:
    name = path.stem
    m = re.search(r"[\-_](\d{1,2})[\-_.]", name)
    return int(m.group(1)) if m else None


def _clean_hs(val) -> str | None:
    if pd.isna(val):
        return None
    s = re.sub(r"[^\d]", "", str(val))
    return s if len(s) >= 2 else None


PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _to_numeric(series: pd.Series) -> pd.Series:
    cleaned = (series.astype(str)
               .str.translate(PERSIAN_DIGITS)
               .str.replace(",", "", regex=False)
               .str.replace(" ", "", regex=False)
               .str.strip())
    return pd.to_numeric(cleaned, errors="coerce")


def _try_read(path: Path, skip: int) -> pd.DataFrame | None:
    for engine in ("openpyxl", "xlrd"):
        try:
            df = pd.read_excel(path, skiprows=skip, dtype=str, engine=engine)
            df.dropna(how="all", inplace=True)
            df.dropna(axis=1, how="all", inplace=True)
            if not df.empty and len(df.columns) >= 3:
                return df
        except Exception:
            continue
    return None


def _has_useful_columns(cols: list[str]) -> bool:
    useful = {"hs_code", "country_name", "value_usd", "net_weight_kg",
              "commodity_description", "customs_office", "value_rial"}
    return bool(useful & set(cols))


def parse_file(path: Path) -> pd.DataFrame | None:
    path = Path(path)
    log.info("Parsing: %s", path.name)

    df = None
    for skip in range(8):
        raw = _try_read(path, skip)
        if raw is None:
            continue
        cols = [_normalize_col(c) for c in raw.columns]
        if _has_useful_columns(cols):
            raw.columns = cols
            df = raw
            break

    if df is None:
        log.warning("No usable header found in %s", path.name)
        return None

    # Drop all-na rows again after header detection
    df.dropna(how="all", inplace=True)

    # Add metadata from filename
    direction = _infer_direction_from_path(path)
    year      = _infer_year_from_path(path)
    month     = _infer_month_from_path(path)

    for col, val in [("direction", direction), ("year", year), ("month", month)]:
        if col not in df.columns and val is not None:
            df[col] = val

    # Normalize direction column values
    if "direction" in df.columns:
        df["direction"] = df["direction"].map(
            lambda v: DIRECTION_MAP.get(str(v).strip(), DIRECTION_MAP.get(str(v).strip().lower(), str(v).strip().lower()))
        )

    # Clean HS codes
    if "hs_code" in df.columns:
        df["hs_code"] = df["hs_code"].apply(_clean_hs)

    # Convert numeric columns
    for col in ("net_weight_kg", "gross_weight_kg", "value_usd", "value_rial",
                "value_cif_usd", "value_fob_usd", "quantity", "year", "month"):
        if col in df.columns:
            df[col] = _to_numeric(df[col])

    # Provenance
    digest = hashlib.md5(path.read_bytes()).hexdigest()[:8]
    df["source_file"] = path.name
    df["file_hash"]   = digest

    log.info("  → %d rows | cols: %s", len(df), list(df.columns))
    return df


def parse_directory(raw_dir: Path) -> pd.DataFrame:
    raw_dir = Path(raw_dir)
    files = sorted(raw_dir.glob("*.xlsx")) + sorted(raw_dir.glob("*.xls"))
    log.info("Found %d Excel files in %s", len(files), raw_dir)

    frames: list[pd.DataFrame] = []
    for f in files:
        df = parse_file(f)
        if df is not None and not df.empty:
            frames.append(df)

    if not frames:
        log.warning("No data parsed")
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    log.info("Combined: %d rows from %d files", len(combined), len(frames))
    return combined


def iter_files(raw_dir: Path) -> Iterator[tuple[Path, pd.DataFrame]]:
    for f in sorted(Path(raw_dir).glob("*.xls*")):
        df = parse_file(f)
        if df is not None and not df.empty:
            yield f, df


if __name__ == "__main__":
    import sys, json
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    raw = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/raw")
    df = parse_directory(raw)
    if not df.empty:
        out = Path("data/processed/combined_trade.parquet")
        out.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(out, index=False)
        print(f"\nSaved {len(df):,} rows → {out}")
        print(df.dtypes.to_string())
