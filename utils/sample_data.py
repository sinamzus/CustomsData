"""
Generates realistic synthetic Iran trade data for development/demo.
Based on approximate real-world proportions from IRICA reports.
"""

import random
import pandas as pd
import numpy as np
from pathlib import Path

random.seed(42)
np.random.seed(42)

# Top export destinations (country_iso3 → approximate share %)
EXPORT_COUNTRIES = {
    "CHN": 28, "IRQ": 18, "ARE": 10, "TUR": 7, "AFG": 5,
    "IND": 4, "PAK": 4, "AZE": 3, "RUS": 3, "KOR": 2,
    "SAU": 2, "EGY": 2, "TKM": 2, "KAZ": 1, "GEO": 1,
    "SYR": 1, "LBN": 1, "JOR": 1, "OMN": 1, "QAT": 1,
}

# Top import sources
IMPORT_COUNTRIES = {
    "CHN": 35, "ARE": 15, "TUR": 10, "DEU": 7, "IND": 5,
    "KOR": 4, "RUS": 4, "BRA": 3, "ITA": 2, "NLD": 2,
    "MYS": 2, "THA": 1, "JPN": 1, "AZE": 1, "UZB": 1,
    "KAZ": 1, "TWN": 1, "GBR": 1, "FRA": 1, "USA": 1,
}

# Transit corridors
TRANSIT_COUNTRIES = {
    "AZE": 20, "TKM": 18, "AFG": 15, "IRQ": 12, "RUS": 10,
    "KAZ": 8, "ARM": 7, "GEO": 5, "TUR": 3, "PAK": 2,
}

# HS chapters with approximate export weights (non-oil)
EXPORT_HS = {
    "27": (35, "سوخت و روغن معدنی"),        # Mineral fuels
    "39": (12, "پلاستیک"),                   # Plastics
    "72": (8, "آهن و فولاد"),               # Iron & Steel
    "28": (6, "مواد شیمیایی معدنی"),        # Inorganic chemicals
    "29": (5, "مواد شیمیایی آلی"),          # Organic chemicals
    "57": (4, "فرش"),                        # Carpets
    "76": (3, "آلومینیوم"),                 # Aluminum
    "08": (3, "میوه‌جات"),                  # Fruits
    "31": (3, "کود شیمیایی"),              # Fertilizers
    "25": (2, "سنگ و خاک معدنی"),          # Minerals
    "73": (2, "مصنوعات فولادی"),           # Steel articles
    "07": (2, "سبزیجات"),                   # Vegetables
    "84": (2, "ماشین‌آلات"),               # Machinery
    "26": (2, "سنگ‌معدن"),                 # Ores
    "74": (2, "مس"),                        # Copper
    "32": (2, "رنگ"),                       # Dyes
    "38": (1, "متفرقه شیمیایی"),           # Misc chemicals
    "40": (1, "لاستیک"),                    # Rubber
    "70": (1, "شیشه"),                      # Glass
    "69": (0, "سرامیک"),                    # Ceramics
}

IMPORT_HS = {
    "84": (22, "ماشین‌آلات مکانیکی"),
    "85": (15, "ماشین‌آلات برقی"),
    "87": (10, "وسائل نقلیه"),
    "72": (8, "آهن و فولاد"),
    "39": (6, "پلاستیک"),
    "10": (5, "غلات"),
    "30": (4, "دارو"),
    "27": (4, "سوخت"),
    "12": (3, "دانه‌های روغنی"),
    "29": (3, "مواد شیمیایی آلی"),
    "15": (3, "روغن‌های گیاهی"),
    "73": (2, "مصنوعات فولادی"),
    "76": (2, "آلومینیوم"),
    "90": (2, "ابزار دقیق"),
    "28": (2, "مواد شیمیایی معدنی"),
    "17": (2, "قند و شکر"),
    "74": (1, "مس"),
    "38": (1, "متفرقه شیمیایی"),
    "40": (1, "لاستیک"),
    "48": (1, "کاغذ"),
}

# Approximate annual totals (billion USD, non-oil exports)
ANNUAL_TOTALS = {
    1379: (4.5, 12.0), 1380: (4.8, 13.0), 1381: (5.2, 14.0),
    1382: (6.1, 17.0), 1383: (7.0, 20.0), 1384: (8.5, 24.0),
    1385: (10.0, 31.0), 1386: (14.0, 40.0), 1387: (19.0, 51.0),
    1388: (20.0, 45.0), 1389: (26.0, 54.0), 1390: (31.0, 62.0),
    1391: (28.0, 57.0), 1392: (25.0, 48.0), 1393: (22.0, 51.0),
    1394: (18.0, 40.0), 1395: (20.0, 36.0), 1396: (24.0, 45.0),
    1397: (20.0, 39.0), 1398: (24.0, 43.0), 1399: (26.0, 38.0),
    1400: (34.0, 57.0), 1401: (53.0, 65.0), 1402: (49.0, 64.0),
    1403: (52.0, 72.0),
}


def _weighted_sample(options: dict, n: int) -> list:
    keys = list(options.keys())
    weights = [options[k] if isinstance(options[k], (int, float)) else options[k][0]
               for k in keys]
    total = sum(weights)
    probs = [w / total for w in weights]
    return np.random.choice(keys, size=n, p=probs).tolist()


def generate_annual_flows(year: int, rows_per_combo: int = 3) -> pd.DataFrame:
    """Generate synthetic trade flow rows for one Shamsi year."""
    exp_total, imp_total = ANNUAL_TOTALS.get(year, (30.0, 50.0))
    records = []

    for direction, countries, hs_map, total_b in [
        ("export", EXPORT_COUNTRIES, EXPORT_HS, exp_total),
        ("import", IMPORT_COUNTRIES, IMPORT_HS, imp_total),
    ]:
        total_usd = total_b * 1e9
        n_records = len(countries) * len(hs_map) * rows_per_combo
        country_samples = _weighted_sample(countries, n_records)
        hs_samples = _weighted_sample(hs_map, n_records)

        for i, (country, hs) in enumerate(zip(country_samples, hs_samples)):
            share = (countries[country] / 100) * (hs_map[hs][0] / 100)
            base_value = total_usd * share / rows_per_combo
            value = max(1000, base_value * np.random.lognormal(0, 0.5))
            weight = value / np.random.uniform(0.5, 3.0)  # USD/kg ratio varies

            records.append({
                "shamsi_year": year,
                "shamsi_month": None,
                "direction": direction,
                "hs_code": f"{hs}0000",
                "hs_chapter": int(hs),
                "commodity_fa": hs_map[hs][1],
                "country_iso3": country,
                "net_weight_kg": round(weight, 1),
                "value_usd": round(value, 2),
            })

    # Transit (weight-based, not value)
    transit_total_tons = {
        1379: 3.0, 1390: 8.0, 1395: 9.5, 1400: 12.0,
        1401: 13.0, 1402: 17.8, 1403: 19.0,
    }.get(year, 7.0) * 1e9  # kg

    n_transit = len(TRANSIT_COUNTRIES) * rows_per_combo
    t_countries = _weighted_sample(TRANSIT_COUNTRIES, n_transit)
    for country in t_countries:
        share = TRANSIT_COUNTRIES[country] / 100
        weight = transit_total_tons * share / rows_per_combo
        records.append({
            "shamsi_year": year,
            "shamsi_month": None,
            "direction": "transit",
            "hs_code": None,
            "hs_chapter": None,
            "commodity_fa": None,
            "country_iso3": country,
            "net_weight_kg": round(weight * np.random.lognormal(0, 0.3), 1),
            "value_usd": None,
        })

    return pd.DataFrame(records)


def generate_all_years(start: int = 1379, end: int = 1403) -> pd.DataFrame:
    frames = [generate_annual_flows(y) for y in range(start, end + 1)]
    df = pd.concat(frames, ignore_index=True)
    return df


def save_sample(path: Path | None = None) -> Path:
    path = path or Path("data/processed/sample_trade.parquet")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df = generate_all_years()
    df.to_parquet(path, index=False)
    print(f"Saved {len(df):,} rows to {path}")
    return Path(path)


if __name__ == "__main__":
    save_sample()
