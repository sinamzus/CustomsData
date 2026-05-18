"""End-to-end pipeline tests with synthetic Excel fixtures."""

import sys
import json
from pathlib import Path
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_export_excel(path: Path):
    """Create a realistic IRICA-style export Excel file."""
    df = pd.DataFrame({
        "کد تعرفه":     ["270900", "390110", "720610", "570110", "840734"],
        "شرح کالا":     ["نفت خام", "پلی اتیلن", "شمش آهن", "فرش دستباف", "موتور بنزینی"],
        "کشور مقصد":    ["چین",    "عراق",    "ترکیه",  "امارات",      "هند"],
        "گمرک":          ["بندر امام خمینی", "پرویزخان", "بازرگان", "فرودگاه مهرآباد", "بندر شهید رجایی"],
        "وزن خالص":     ["1500000", "85000", "250000", "2500", "12000"],
        "ارزش دلاری":   ["750000", "42500", "87500", "45000", "8400"],
        "ارزش ریالی":   ["31500000000", "1785000000", "3675000000", "1890000000", "352800000"],
    })
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(path, index=False)


def make_import_excel(path: Path):
    """Import file with Persian digit amounts and extra header row."""
    header_info = pd.DataFrame([["گزارش آمار واردات سال ۱۴۰۲", "", "", "", "", "", ""]])
    df = pd.DataFrame({
        "کد تعرفه":   ["840734", "851712", "100190", "300490", "391010"],
        "شرح کالا":   ["موتور خودرو", "گوشی موبایل", "گندم", "داروی سرماخوردگی", "پلاستیک خاص"],
        "کشور مبدا":  ["آلمان", "چین", "روسیه", "هند", "ترکیه"],
        "گمرک":        ["فرودگاه امام", "بندر شهید رجایی", "لطف‌آباد", "فرودگاه مهرآباد", "بازرگان"],
        "وزن خالص":   ["۸۵۰۰۰", "۱۲۰۰۰", "۵۰۰۰۰۰۰", "۳۵۰۰", "۹۵۰۰۰"],
        "ارزش(دلار)": ["۳۲۰۰۰۰", "۱۸۰۰۰۰", "۱۱۰۰۰۰۰", "۷۵۰۰۰", "۴۷۵۰۰"],
        "ارزش(ريال)": ["13440000000", "7560000000", "46200000000", "3150000000", "1995000000"],
    })
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as w:
        header_info.to_excel(w, index=False, header=False)
        df.to_excel(w, index=False, startrow=1)


def make_transit_excel(path: Path):
    df = pd.DataFrame({
        "کشور مبدا":    ["آذربایجان", "ترکمنستان", "افغانستان"],
        "کشور مقصد":    ["روسیه",    "قزاقستان",  "امارات"],
        "گمرک":          ["آستارا",   "سرخس",      "پرویزخان"],
        "وزن خالص":     ["2000000",  "3500000",   "1500000"],
        "نوع معامله":   ["ترانزیت",  "ترانزیت",   "ترانزیت"],
    })
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(path, index=False)


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_parse_export(tmp_path):
    f = tmp_path / "export_1402.xlsx"
    make_export_excel(f)
    from parser.excel_parser import parse_file
    df = parse_file(f)
    assert df is not None
    assert len(df) == 5
    assert "hs_code" in df.columns
    assert df["hs_code"].notna().all()
    assert df["net_weight_kg"].notna().all()
    assert df["value_usd"].notna().all()
    assert (df["direction"] == "export").all()
    assert df["year"].iloc[0] == 1402


def test_parse_import_persian_digits(tmp_path):
    f = tmp_path / "import_1402.xlsx"
    make_import_excel(f)
    from parser.excel_parser import parse_file
    df = parse_file(f)
    assert df is not None
    assert len(df) == 5
    # Persian ۸۵۰۰۰ should parse to 85000
    assert float(df[df["hs_code"] == "840734"]["net_weight_kg"].iloc[0]) == 85000.0


def test_parse_transit(tmp_path):
    f = tmp_path / "transit_1402.xlsx"
    make_transit_excel(f)
    from parser.excel_parser import parse_file
    df = parse_file(f)
    assert df is not None
    assert (df["direction"] == "transit").all()


def test_country_normalization():
    from data.mappings.country_mapping import normalize_country
    assert normalize_country("چین") == "CHN"
    assert normalize_country("جمهوری خلق چین") == "CHN"
    assert normalize_country("CHINA") == "CHN"
    assert normalize_country("امارات متحده عربی") == "ARE"
    assert normalize_country("ناشناس") is None
    assert normalize_country("") is None


def test_hs_enrichment():
    from data.mappings.hs_sections import get_chapter, get_section, HS_CHAPTERS
    assert get_chapter("270900") == 27
    assert get_section("270900") == 5     # Mineral Products
    assert get_chapter("840734") == 84
    assert get_section("840734") == 16    # Machinery
    assert get_chapter("570110") == 57
    assert get_section("570110") == 11    # Textiles (Carpets)


def test_normalizer_full_pipeline(tmp_path):
    f = tmp_path / "export_1402.xlsx"
    make_export_excel(f)
    from parser.excel_parser import parse_file
    from utils.normalizer import run_all, quality_report
    df = parse_file(f)
    df_norm = run_all(df)
    assert "country_iso3" in df_norm.columns
    assert "hs_chapter" in df_norm.columns
    assert "hs_section" in df_norm.columns
    assert "miladi_year" in df_norm.columns
    assert df_norm["country_iso3"].notna().all()
    report = quality_report(df_norm)
    assert report["country_iso3_null_pct"] == 0.0
    assert report["hs_code_null_pct"] == 0.0
    assert report["year_range"] == [1402, 1402]


def test_sample_data_generator():
    from utils.sample_data import generate_annual_flows
    df = generate_annual_flows(1402)
    assert len(df) > 100
    assert set(df["direction"].unique()) >= {"export", "import", "transit"}
    exports = df[df["direction"] == "export"]
    assert exports["value_usd"].sum() > 1e9


def test_api_store_summary():
    import api.store as store
    store._df = None
    store.load()
    s = store.summary(1402)
    assert s["export"]["value_usd"] > 0
    assert s["import"]["value_usd"] > 0
    assert len(s["available_years"]) > 10


def test_api_store_flows():
    import api.store as store
    flows = store.map_flows(1402, "export", top_n=10)
    assert len(flows) > 0
    assert all("country" in f and "lat" in f and "lng" in f for f in flows)
    assert all(f["value_usd"] >= 0 for f in flows)


def test_api_store_timeseries():
    import api.store as store
    ts = store.timeseries(country="CHN", direction="export", hs_chapter=None)
    assert len(ts) > 10
    years = [t["year"] for t in ts]
    assert years == sorted(years)


def test_api_store_treemap():
    import api.store as store
    tm = store.treemap(1402, "export")
    assert len(tm) > 5
    assert tm[0]["value_usd"] >= tm[-1]["value_usd"]  # sorted descending
