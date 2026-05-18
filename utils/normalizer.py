"""
Post-parse normalization: country ISO lookup, HS enrichment,
direction inference, and data quality checks.
"""

import logging
import pandas as pd

from data.mappings.country_mapping import normalize_country
from data.mappings.hs_sections import enrich_hs, get_chapter

log = logging.getLogger(__name__)

SHAMSI_TO_MILADI_OFFSET = 621  # approximate


def add_country_iso(df: pd.DataFrame) -> pd.DataFrame:
    if "country_name" not in df.columns:
        return df
    df = df.copy()
    df["country_iso3"] = df["country_name"].apply(normalize_country)
    unmatched = df.loc[df["country_iso3"].isna() & df["country_name"].notna(), "country_name"].unique()
    if len(unmatched):
        log.warning("Unmatched country names (%d): %s", len(unmatched), list(unmatched[:10]))
    return df


def normalize_direction(df: pd.DataFrame) -> pd.DataFrame:
    if "direction" not in df.columns:
        return df
    mapping = {
        "صادرات": "export", "export": "export",
        "واردات": "import", "import": "import",
        "ترانزیت": "transit", "ترانزيت": "transit", "transit": "transit",
    }
    df = df.copy()
    df["direction"] = df["direction"].map(lambda v: mapping.get(str(v).strip(), str(v).strip().lower()))
    return df


def add_miladi_year(df: pd.DataFrame) -> pd.DataFrame:
    """Add approximate Miladi year for reference."""
    if "year" in df.columns:
        df = df.copy()
        df["miladi_year"] = pd.to_numeric(df["year"], errors="coerce") + SHAMSI_TO_MILADI_OFFSET
    return df


def clip_weights(df: pd.DataFrame) -> pd.DataFrame:
    """Remove physically impossible weight values (>1M tons per row)."""
    df = df.copy()
    for col in ("net_weight_kg", "gross_weight_kg"):
        if col in df.columns:
            mask = df[col] > 1e9
            if mask.any():
                log.warning("Clipping %d suspiciously large %s values", mask.sum(), col)
                df.loc[mask, col] = None
    return df


def run_all(df: pd.DataFrame) -> pd.DataFrame:
    """Apply all normalization steps in sequence."""
    df = normalize_direction(df)
    df = add_country_iso(df)
    enrich_hs(df)
    df = add_miladi_year(df)
    df = clip_weights(df)
    return df


def quality_report(df: pd.DataFrame) -> dict:
    """Return a dict with basic data quality metrics."""
    report = {
        "total_rows": len(df),
        "columns": list(df.columns),
    }
    for col in ("hs_code", "country_iso3", "direction", "year", "value_usd", "net_weight_kg"):
        if col in df.columns:
            null_pct = df[col].isna().mean() * 100
            report[f"{col}_null_pct"] = round(null_pct, 1)
    if "direction" in df.columns:
        report["direction_counts"] = df["direction"].value_counts().to_dict()
    if "year" in df.columns:
        valid_years = pd.to_numeric(df["year"], errors="coerce").dropna()
        if not valid_years.empty:
            report["year_range"] = [int(valid_years.min()), int(valid_years.max())]
    if "country_iso3" in df.columns:
        report["unique_countries"] = int(df["country_iso3"].nunique())
    if "hs_code" in df.columns:
        report["unique_hs_codes"] = int(df["hs_code"].nunique())
    return report
