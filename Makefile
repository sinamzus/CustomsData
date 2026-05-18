.PHONY: help install dev scrape parse normalize load run report docker-up docker-down docker-build

# ── Local dev ──────────────────────────────────────────────────────────────
help:
	@echo "Iran Trade Map — available commands"
	@echo ""
	@echo "  make install      Install Python dependencies"
	@echo "  make dev          Start API server with auto-reload (http://localhost:8000)"
	@echo "  make scrape       Download Excel files from irica.ir → data/raw/"
	@echo "  make parse        Parse downloaded Excel files → data/processed/"
	@echo "  make normalize    Normalize country/HS codes + quality report"
	@echo "  make run          Full pipeline: scrape + parse + normalize"
	@echo "  make report       Show data quality report"
	@echo ""
	@echo "  make docker-build Build Docker image"
	@echo "  make docker-up    Start full stack (API + PostgreSQL + Nginx)"
	@echo "  make docker-down  Stop stack"
	@echo ""
	@echo "  make register FILE=~/Downloads/export_1402.xlsx YEAR=1402 DIR=export"
	@echo "              Register a manually downloaded file"

install:
	pip install -r requirements.txt

dev:
	uvicorn api.main:app --reload --port 8000

# ── ETL pipeline ──────────────────────────────────────────────────────────
scrape:
	python pipeline.py scrape

parse:
	python pipeline.py parse

normalize:
	python pipeline.py normalize

run:
	python pipeline.py run

report:
	python pipeline.py report

load:
	python pipeline.py load --db $${DATABASE_URL}

# Register a manually placed file (set FILE, YEAR, DIR env vars)
FILE  ?= data/raw/manual.xlsx
YEAR  ?= 1402
DDIR  ?= export
register:
	python -c "from scraper.irica_scraper import register_manual; register_manual('$(FILE)', $(YEAR), '$(DDIR)')"

# ── Docker ────────────────────────────────────────────────────────────────
docker-build:
	docker build -t iran-trade-map .

docker-up:
	cd deploy && docker compose --env-file ../.env up -d

docker-down:
	cd deploy && docker compose down

docker-logs:
	cd deploy && docker compose logs -f api
