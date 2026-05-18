"""
HS Code section and chapter metadata.
Maps HS chapter (2-digit) → section and Persian/English description.
"""

# Chapter number → (section_number, section_name_en, section_name_fa)
HS_CHAPTERS: dict[int, tuple[int, str, str]] = {
    1:  (1, "Live Animals", "حیوانات زنده"),
    2:  (1, "Meat & Edible Offal", "گوشت"),
    3:  (1, "Fish & Seafood", "ماهی و آبزیان"),
    4:  (1, "Dairy, Eggs, Honey", "لبنیات، تخم‌مرغ، عسل"),
    5:  (1, "Other Animal Products", "سایر محصولات حیوانی"),
    6:  (2, "Live Plants", "گیاهان زنده"),
    7:  (2, "Vegetables", "سبزیجات"),
    8:  (2, "Fruits & Nuts", "میوه‌جات"),
    9:  (2, "Coffee, Tea, Spices", "قهوه، چای، ادویه"),
    10: (2, "Cereals", "غلات"),
    11: (2, "Milling Products", "محصولات آسیاب"),
    12: (2, "Oil Seeds", "دانه‌های روغنی"),
    13: (2, "Resins & Extracts", "رزین‌ها و عصاره‌ها"),
    14: (2, "Vegetable Plaiting", "مواد گیاهی بافندگی"),
    15: (3, "Fats & Oils", "چربی‌ها و روغن‌ها"),
    16: (4, "Prepared Meat/Fish", "کنسرو گوشت و ماهی"),
    17: (4, "Sugars", "قند و شکر"),
    18: (4, "Cocoa", "کاکائو"),
    19: (4, "Cereal Preparations", "فرآورده‌های غلات"),
    20: (4, "Vegetable Preparations", "فرآورده‌های سبزیجات"),
    21: (4, "Miscellaneous Food", "متفرقه خوراکی"),
    22: (4, "Beverages", "نوشیدنی‌ها"),
    23: (4, "Animal Feed", "خوراک دام"),
    24: (4, "Tobacco", "توتون و تنباکو"),
    25: (5, "Minerals & Salt", "مواد معدنی و نمک"),
    26: (5, "Ores & Slag", "سنگ‌معدن و سرباره"),
    27: (5, "Mineral Fuels & Oil", "سوخت معدنی و نفت"),
    28: (6, "Inorganic Chemicals", "مواد شیمیایی غیرآلی"),
    29: (6, "Organic Chemicals", "مواد شیمیایی آلی"),
    30: (6, "Pharmaceuticals", "داروها"),
    31: (6, "Fertilizers", "کودهای شیمیایی"),
    32: (6, "Dyes & Pigments", "رنگ‌ها و رنگدانه‌ها"),
    33: (6, "Perfumes & Cosmetics", "عطر و لوازم آرایشی"),
    34: (6, "Soaps & Detergents", "صابون و شوینده‌ها"),
    35: (6, "Albumins & Enzymes", "آلبومین‌ها و آنزیم‌ها"),
    36: (6, "Explosives", "مواد منفجره"),
    37: (6, "Photographic", "محصولات عکاسی"),
    38: (6, "Miscellaneous Chemicals", "متفرقه شیمیایی"),
    39: (7, "Plastics", "پلاستیک"),
    40: (7, "Rubber", "لاستیک"),
    41: (8, "Hides & Skins", "پوست خام"),
    42: (8, "Leather Goods", "کالاهای چرمی"),
    43: (8, "Furskins", "پوستین"),
    44: (9, "Wood", "چوب"),
    45: (9, "Cork", "چوب‌پنبه"),
    46: (9, "Basketwork", "بافته‌های چوبی"),
    47: (10, "Wood Pulp", "خمیر کاغذ"),
    48: (10, "Paper & Paperboard", "کاغذ و مقوا"),
    49: (10, "Printed Books", "کتب چاپی"),
    50: (11, "Silk", "ابریشم"),
    51: (11, "Wool", "پشم"),
    52: (11, "Cotton", "پنبه"),
    53: (11, "Other Vegetable Fibers", "الیاف گیاهی"),
    54: (11, "Man-made Filaments", "الیاف مصنوعی"),
    55: (11, "Man-made Staple Fibers", "الیاف کوتاه مصنوعی"),
    56: (11, "Wadding & Felt", "نمد و آوات"),
    57: (11, "Carpets", "فرش"),
    58: (11, "Special Woven Fabrics", "پارچه‌های بافته ویژه"),
    59: (11, "Impregnated Textiles", "منسوجات آغشته"),
    60: (11, "Knitted Fabrics", "پارچه‌های کشباف"),
    61: (11, "Knitted Apparel", "پوشاک کشباف"),
    62: (11, "Woven Apparel", "پوشاک بافته"),
    63: (11, "Other Textiles", "سایر منسوجات"),
    64: (12, "Footwear", "کفش"),
    65: (12, "Headgear", "کلاه"),
    66: (12, "Umbrellas", "چتر"),
    67: (12, "Feathers & Artificial Flowers", "پر و گل مصنوعی"),
    68: (13, "Stone & Cement", "سنگ و سیمان"),
    69: (13, "Ceramics", "سرامیک"),
    70: (13, "Glass", "شیشه"),
    71: (14, "Precious Metals & Gems", "فلزات گرانبها و سنگ‌قیمتی"),
    72: (15, "Iron & Steel", "آهن و فولاد"),
    73: (15, "Iron/Steel Articles", "مصنوعات آهن و فولاد"),
    74: (15, "Copper", "مس"),
    75: (15, "Nickel", "نیکل"),
    76: (15, "Aluminum", "آلومینیوم"),
    78: (15, "Lead", "سرب"),
    79: (15, "Zinc", "روی"),
    80: (15, "Tin", "قلع"),
    81: (15, "Other Base Metals", "سایر فلزات پایه"),
    82: (15, "Tools & Cutlery", "ابزار و کارد"),
    83: (15, "Miscellaneous Metal", "متفرقه فلزی"),
    84: (16, "Machinery & Mechanical", "ماشین‌آلات مکانیکی"),
    85: (16, "Electrical Machinery", "ماشین‌آلات برقی"),
    86: (17, "Railway", "راه‌آهن"),
    87: (17, "Vehicles", "وسائل نقلیه"),
    88: (17, "Aircraft", "هواپیما"),
    89: (17, "Ships & Boats", "کشتی"),
    90: (18, "Optical & Medical", "اپتیک و پزشکی"),
    91: (18, "Clocks & Watches", "ساعت"),
    92: (18, "Musical Instruments", "آلات موسیقی"),
    93: (19, "Arms & Ammunition", "اسلحه"),
    94: (20, "Furniture", "مبل"),
    95: (20, "Toys & Games", "اسباب‌بازی"),
    96: (20, "Miscellaneous Manufactured", "متفرقه ساخته‌شده"),
    97: (21, "Art & Antiques", "هنر و عتیقه‌جات"),
}

HS_SECTIONS: dict[int, tuple[str, str]] = {
    1:  ("Live Animals & Products", "حیوانات زنده و فرآورده‌ها"),
    2:  ("Vegetable Products", "محصولات گیاهی"),
    3:  ("Fats & Oils", "چربی‌ها و روغن‌ها"),
    4:  ("Prepared Foodstuffs", "مواد غذایی آماده"),
    5:  ("Mineral Products", "محصولات معدنی"),
    6:  ("Chemical Products", "محصولات شیمیایی"),
    7:  ("Plastics & Rubber", "پلاستیک و لاستیک"),
    8:  ("Hides & Leather", "پوست و چرم"),
    9:  ("Wood & Wood Products", "چوب و فرآورده‌ها"),
    10: ("Paper & Pulp", "کاغذ و خمیر"),
    11: ("Textiles", "منسوجات"),
    12: ("Footwear & Headgear", "کفش و کلاه"),
    13: ("Stone, Ceramic, Glass", "سنگ، سرامیک، شیشه"),
    14: ("Precious Metals", "فلزات گرانبها"),
    15: ("Base Metals", "فلزات پایه"),
    16: ("Machinery & Electronics", "ماشین‌آلات و الکترونیک"),
    17: ("Transportation", "حمل‌ونقل"),
    18: ("Precision Instruments", "ابزار دقیق"),
    19: ("Arms", "اسلحه"),
    20: ("Miscellaneous Manufactured", "ساخته‌شده متفرقه"),
    21: ("Art & Antiques", "هنر و عتیقه"),
}


def get_chapter(hs_code: str) -> int | None:
    if not hs_code:
        return None
    digits = "".join(c for c in str(hs_code) if c.isdigit())
    if len(digits) >= 2:
        return int(digits[:2])
    return None


def get_section(hs_code: str) -> int | None:
    chapter = get_chapter(hs_code)
    if chapter is None:
        return None
    return HS_CHAPTERS.get(chapter, (None,))[0]


def enrich_hs(df) -> None:
    """Add hs_chapter and hs_section columns in-place."""
    import pandas as pd
    if "hs_code" not in df.columns:
        return
    df["hs_chapter"] = df["hs_code"].apply(get_chapter)
    df["hs_section"] = df["hs_code"].apply(get_section)
