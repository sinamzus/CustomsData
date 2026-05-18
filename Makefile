.PHONY: help install check scrape parse normalize run demo report load \
        dev docker-build docker-up docker-down docker-logs test

help:
	@echo ""
	@echo "  ── Iran Trade Map ──────────────────────────────────────"
	@echo ""
	@echo "  First time setup:"
	@echo "    make install          Install Python dependencies"
	@echo "    make check            Test connectivity to irica.ir"
	@echo ""
	@echo "  With real data (needs Iran network access):"
	@echo "    make scrape           Download Excel files from irica.ir"
	@echo "    make parse            Parse Excel → Parquet"
	@echo "    make normalize        Normalize + quality report"
	@echo "    make run              All three steps above"
	@echo "    make dev              Start API at http://localhost:8000"
	@echo ""
	@echo "  Without real data (demo mode):"
	@echo "    make demo             Generate sample data + start API"
	@echo ""
	@echo "  Production (Docker):"
	@echo "    make docker-build     Build Docker image"
	@echo "    make docker-up        Start API + PostgreSQL + Nginx"
	@echo "    make docker-down      Stop all containers"
	@echo "    make docker-logs      Tail API logs"
	@echo ""
	@echo "  Other:"
	@echo "    make test             Run test suite"
	@echo "    make report           Data quality report"
	@echo "    make register FILE=path/to/file.xlsx YEAR=1402 DDIR=export"
	@echo ""

install:
	pip install -r requirements.txt

# ── Data pipeline ─────────────────────────────────────────────────────────
check:
	python pipeline.py check

scrape:
	python pipeline.py scrape

parse:
	python pipeline.py parse

normalize:
	python pipeline.py normalize

run:
	python pipeline.py run

demo:
	python pipeline.py demo

report:
	python pipeline.py report

load:
	python pipeline.py load --db $${DATABASE_URL}

# Register a manually placed Excel file
# Usage: make register FILE=~/Downloads/export_1402.xlsx YEAR=1402 DDIR=export
FILE ?= ""
YEAR ?= 1402
DDIR ?= export
register:
	@python -c "from scraper.irica_scraper import register_manual; register_manual('$(FILE)', $(YEAR), '$(DDIR)')"
	@echo "File registered. Run 'make parse' to process it."

# ── Dev server ────────────────────────────────────────────────────────────
dev:
	uvicorn api.main:app --reload --port 8000

# ── Tests ─────────────────────────────────────────────────────────────────
test:
	python -m pytest tests/ -v

# ── Docker ────────────────────────────────────────────────────────────────
docker-build:
	docker build -t iran-trade-map .

docker-up:
	cd deploy && docker compose --env-file ../.env up -d
	@echo "Stack running:"
	@echo "  API   → http://localhost:8000"
	@echo "  Web   → http://localhost:80"

docker-down:
	cd deploy && docker compose down

docker-logs:
	cd deploy && docker compose logs -f api
