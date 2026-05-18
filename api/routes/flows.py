from fastapi import APIRouter, Query
from typing import Literal
import api.store as store

router = APIRouter(prefix="/flows", tags=["flows"])

Direction = Literal["export", "import", "transit"]


@router.get("/map")
def get_map_flows(
    year: int = Query(1402, description="Shamsi year"),
    direction: Direction = Query("export"),
    top_n: int = Query(50, ge=1, le=200),
):
    """Arc data for Deck.gl map: top N partner countries with value/weight."""
    return store.map_flows(year=year, direction=direction, top_n=top_n)


@router.get("/timeseries")
def get_timeseries(
    country: str | None = Query(None, description="ISO 3166-1 alpha-3 e.g. CHN"),
    direction: Direction | None = Query(None),
    hs_chapter: int | None = Query(None, description="2-digit HS chapter e.g. 27"),
):
    """Annual trade totals filtered by country / direction / HS chapter."""
    return store.timeseries(country=country, direction=direction, hs_chapter=hs_chapter)


@router.get("/treemap")
def get_treemap(
    year: int = Query(1402),
    direction: Direction = Query("export"),
):
    """Commodity breakdown by HS chapter for treemap visualization."""
    return store.treemap(year=year, direction=direction)


@router.get("/partners")
def get_top_partners(
    year: int = Query(1402),
    direction: Direction = Query("export"),
    n: int = Query(15, ge=1, le=50),
):
    """Ranked list of top trade partners for a given year/direction."""
    return store.top_partners(year=year, direction=direction, n=n)
