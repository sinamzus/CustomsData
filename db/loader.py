"""
Database loader — inserts normalized trade DataFrames into PostgreSQL.
Requires: psycopg2-binary, SQLAlchemy
"""

import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

try:
    from sqlalchemy import create_engine, text
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False
    log.warning("SQLAlchemy not installed — DB loading disabled")


def get_engine(db_url: str):
    if not HAS_SQLALCHEMY:
        raise RuntimeError("Install sqlalchemy and psycopg2-binary")
    return create_engine(db_url, pool_pre_ping=True)


def init_schema(engine) -> None:
    schema_path = Path(__file__).parent / "schema.sql"
    sql = schema_path.read_text()
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
    log.info("Schema initialized")


def seed_reference_tables(engine) -> None:
    """Insert HS sections/chapters and country metadata."""
    from data.mappings.hs_sections import HS_CHAPTERS, HS_SECTIONS
    from data.mappings.country_mapping import COUNTRY_META

    with engine.connect() as conn:
        # HS Sections
        for sec_id, (name_en, name_fa) in HS_SECTIONS.items():
            conn.execute(text(
                "INSERT INTO hs_sections (section, name_en, name_fa) "
                "VALUES (:s, :en, :fa) ON CONFLICT DO NOTHING"
            ), {"s": sec_id, "en": name_en, "fa": name_fa})

        # HS Chapters
        for chapter, (section, name_en, name_fa) in HS_CHAPTERS.items():
            conn.execute(text(
                "INSERT INTO hs_chapters (chapter, section, name_en, name_fa) "
                "VALUES (:c, :s, :en, :fa) ON CONFLICT DO NOTHING"
            ), {"c": chapter, "s": section, "en": name_en, "fa": name_fa})

        # Countries
        for iso3, meta in COUNTRY_META.items():
            conn.execute(text(
                "INSERT INTO countries (iso3, name_en, name_fa, region, continent) "
                "VALUES (:iso3, :en, :fa, :reg, :cont) ON CONFLICT DO NOTHING"
            ), {
                "iso3": iso3, "en": meta["name_en"], "fa": meta["name_fa"],
                "reg": meta.get("region"), "cont": meta.get("continent"),
            })

        conn.commit()
    log.info("Reference tables seeded")


def load_dataframe(df: pd.DataFrame, engine, batch_size: int = 5000) -> int:
    """
    Insert a normalized trade DataFrame into trade_flows table.
    Returns number of rows inserted.
    """
    col_map = {
        "year": "shamsi_year",
        "month": "shamsi_month",
        "direction": "direction",
        "hs_code": "hs_code",
        "hs_chapter": "hs_chapter",
        "commodity_description": "commodity_fa",
        "country_iso3": "country_iso3",
        "country_name": "country_raw",
        "customs_office": "customs_raw",
        "province": "province",
        "net_weight_kg": "net_weight_kg",
        "gross_weight_kg": "gross_weight_kg",
        "quantity": "quantity",
        "value_usd": "value_usd",
        "value_rial": "value_rial",
        "value_cif_usd": "value_cif_usd",
        "value_fob_usd": "value_fob_usd",
        "source_file": "source_file",
        "file_hash": "file_hash",
    }

    # Keep only columns we have
    available = {k: v for k, v in col_map.items() if k in df.columns}
    out = df[list(available.keys())].rename(columns=available)

    # Ensure mandatory column
    if "shamsi_year" not in out.columns:
        log.warning("No year column — skipping load")
        return 0

    total = 0
    for start in range(0, len(out), batch_size):
        chunk = out.iloc[start:start + batch_size]
        chunk.to_sql(
            "trade_flows",
            engine,
            if_exists="append",
            index=False,
            method="multi",
        )
        total += len(chunk)
        log.info("  Inserted rows %d–%d", start, start + len(chunk))

    return total
