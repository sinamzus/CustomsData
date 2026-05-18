# نقشه تجارت ایران — Iran Trade Map

نقشه تعاملی تجارت خارجی ایران بر اساس داده‌های گمرک جمهوری اسلامی ایران (IRICA).

![stack](https://img.shields.io/badge/FastAPI-0.111-green) ![stack](https://img.shields.io/badge/Python-3.11-blue) ![stack](https://img.shields.io/badge/Deck.gl-9.x-orange)

---

## ویژگی‌ها

- **نقشه کمان‌ها** — جریان صادرات/واردات ایران با تمام کشورها روی نقشه جهانی
- **ترکیب کالایی** — Treemap فصل‌های HS با برچسب فارسی
- **سری زمانی** — روند تجارت از ۱۳۷۱ تا امروز
- **شرکای برتر** — رتبه‌بندی کشورها به همراه سهم درصدی
- **پوشش کامل** — صادرات، واردات، ترانزیت
- **آپدیت ماهانه** — sync خودکار از irica.ir

---

## شروع سریع

```bash
git clone <repo-url>
cd CustomsData
pip install -r requirements.txt
```

### حالت Demo (بدون نیاز به داده واقعی)
```bash
make demo
# → http://localhost:8000
```

### حالت واقعی (نیاز به دسترسی به شبکه ایران)
```bash
make check        # تست اتصال به irica.ir
make run          # دانلود + parse + normalize
make dev          # اجرای API
```

---

## معماری

```
irica.ir (Excel ماهانه)
        │
        ▼
scraper/irica_scraper.py   ← دانلود و کشف لینک‌های Excel
        │
        ▼
parser/excel_parser.py     ← parse + نرمال‌سازی header (90+ نوع)
        │
        ▼
utils/normalizer.py        ← کشور → ISO3، HS chapter/section
        │
        ▼
data/processed/*.parquet   ← ذخیره بهینه
        │
        ▼
api/main.py (FastAPI)      ← 5 endpoint
        │
        ▼
frontend/ (Deck.gl + Plotly) ← داشبورد تعاملی
```

---

## دستورات pipeline

| دستور | کار |
|-------|-----|
| `make check` | تست اتصال به irica.ir |
| `make scrape` | دانلود فایل‌های Excel از irica.ir |
| `make parse` | تبدیل Excel → Parquet |
| `make normalize` | نرمال‌سازی + گزارش کیفیت داده |
| `make run` | سه مرحله بالا یکجا |
| `make demo` | داده نمونه + API |
| `make dev` | API server در localhost:8000 |
| `make test` | اجرای تست‌ها |

### اضافه کردن فایل دستی
اگر فایل Excel را جداگانه دانلود کرده‌اید:
```bash
make register FILE=~/Downloads/export_1402.xlsx YEAR=1402 DDIR=export
make parse
make normalize
```

---

## API Endpoints

| Method | Path | توضیح |
|--------|------|-------|
| GET | `/api/summary?year=1402` | خلاصه: صادرات، واردات، تراز، ترانزیت |
| GET | `/api/years` | لیست سال‌های موجود |
| GET | `/api/flows/map?year=1402&direction=export` | داده arc برای نقشه |
| GET | `/api/flows/timeseries?country=CHN&direction=export` | سری زمانی |
| GET | `/api/flows/treemap?year=1402&direction=export` | ترکیب کالایی HS |
| GET | `/api/flows/partners?year=1402&direction=export&n=15` | شرکای برتر |

مستندات کامل: `http://localhost:8000/docs`

---

## Docker (Production)

```bash
cp .env.example .env          # DB_PASSWORD را تنظیم کنید
make docker-up                # API + PostgreSQL + Nginx
# → http://localhost
```

---

## ساختار پروژه

```
CustomsData/
├── pipeline.py              ← CLI اصلی
├── Makefile                 ← دستورات shortcut
├── Dockerfile
├── deploy/
│   ├── docker-compose.yml
│   └── nginx.conf
├── scraper/
│   └── irica_scraper.py     ← دانلود از irica.ir
├── parser/
│   └── excel_parser.py      ← parse Excel
├── data/
│   ├── raw/                 ← فایل‌های Excel خام (git-ignored)
│   ├── processed/           ← Parquet (git-ignored)
│   └── mappings/
│       ├── country_mapping.py   ← 120+ نام کشور → ISO3
│       └── hs_sections.py       ← HS فصل‌ها با برچسب فارسی
├── utils/
│   ├── normalizer.py        ← نرمال‌سازی داده
│   └── sample_data.py       ← داده نمونه (۶۰K ردیف)
├── db/
│   ├── schema.sql           ← PostgreSQL schema
│   └── loader.py            ← batch loader
├── api/
│   ├── main.py              ← FastAPI app
│   ├── store.py             ← query engine
│   ├── geo.py               ← مختصات کشورها
│   └── routes/flows.py      ← API routes
├── frontend/
│   ├── index.html
│   └── static/
│       ├── css/style.css
│       └── js/app.js
└── tests/
    └── test_pipeline.py     ← 11 test ✅
```

---

## منبع داده

داده از دفتر آمار و پردازش اطلاعات گمرکی، وب‌سایت رسمی [irica.ir](https://www.irica.ir) دریافت می‌شود.
فایل‌های Excel ماهانه از سال ۱۳۷۱ به صورت عمومی منتشر می‌شوند.
