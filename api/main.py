"""
Iran Trade Map — FastAPI Backend
Run: uvicorn api.main:app --reload --port 8000
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

import api.store as store
from api.routes.flows import router as flows_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.load()
    yield


app = FastAPI(
    title="Iran Trade Map API",
    description="نقشه تجارت ایران — داده‌های گمرک جمهوری اسلامی ایران",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(flows_router, prefix="/api")


@app.get("/api/summary")
def get_summary(year: int | None = Query(None, description="Shamsi year")):
    """Overall trade summary: totals, balance, available years."""
    return store.summary(year=year)


@app.get("/api/years")
def get_years():
    """List all available Shamsi years in the dataset."""
    return store.available_years()


# ── Serve frontend ────────────────────────────────────────────────────────────
_frontend = Path(__file__).parent.parent / "frontend"
if _frontend.exists():
    app.mount("/static", StaticFiles(directory=str(_frontend / "static")), name="static")

    @app.get("/", include_in_schema=False)
    def root():
        return FileResponse(str(_frontend / "index.html"))
