"""
routes/news.py — Live Disaster News API Endpoints
==================================================
FastAPI router exposing the aggregated news data.

Endpoints:
  GET /api/v1/news/map-layers   → GeoJSON FeatureCollection (Leaflet-ready)
  GET /api/v1/news/feed         → Paginated JSON list (news panel)
  GET /api/v1/news/status       → Worker health + stats
  POST /api/v1/news/refresh     → Force immediate re-ingestion cycle
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session
import pandas as pd
import io
import json

from database import get_db, Incident, SessionLocal, AggregatedEvent
from news_aggregator.cache import news_cache
from news_aggregator.fetcher import run_ingestion_pipeline

logger = logging.getLogger("routes.news")
router = APIRouter()


# ─── Endpoint 1: GeoJSON Map Layer ───────────────────────────────────────────

@router.get(
    "/map-layers",
    summary="Live Disaster News — GeoJSON FeatureCollection",
    description=(
        "Returns a GeoJSON FeatureCollection of all aggregated and clustered "
        "disaster incidents from the last 24 hours. Each Feature point is enriched "
        "with trust score, hazard category, source provenance, and media links. "
        "Leaflet.js compatible. Refreshed every 10 seconds by the background worker."
    ),
    response_class=JSONResponse,
)
async def get_map_layers():
    """
    Primary Leaflet.js data endpoint.
    Returns cached GeoJSON — sub-millisecond response time.
    Falls back to a live ingestion cycle if cache is cold (first request).
    """
    geojson = await news_cache.get("geojson_layer")

    if geojson is None:
        logger.info("[API] Cache cold — triggering synchronous ingestion for first request")
        await run_ingestion_pipeline()
        geojson = await news_cache.get("geojson_layer")

    if geojson is None:
        # Return empty FeatureCollection rather than 500 error
        return JSONResponse({
            "type": "FeatureCollection",
            "metadata": {
                "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "item_count": 0,
                "temporal_window_hours": 48,
                "message": "Ingestion in progress — check back in a few seconds",
            },
            "features": [],
        }, headers=_cors_headers())

    return JSONResponse(geojson, headers=_cors_headers())


# ─── Endpoint 2: Paginated Feed ───────────────────────────────────────────────

@router.get(
    "/feed",
    summary="Live Disaster News — Paginated JSON Feed",
    description=(
        "Returns a paginated, trust-score-sorted list of disaster incident clusters. "
        "Ideal for rendering the right-side news panel. "
        "Sorted: trust_score DESC, then published_at DESC."
    ),
)
async def get_news_feed(
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(default=20, ge=1, le=100, description="Items per page"),
    category: Optional[str] = Query(default=None, description="Filter by hazard category"),
    min_trust: Optional[float] = Query(default=None, ge=0, le=100, description="Minimum trust score"),
):
    """
    Paginated news feed with optional category and trust score filtering.
    """
    feed = await news_cache.get("feed_list")

    if feed is None:
        logger.info("[API] Cache cold — triggering synchronous ingestion")
        await run_ingestion_pipeline()
        feed = await news_cache.get("feed_list") or []

    # Apply filters
    filtered = feed
    if category:
        filtered = [item for item in filtered
                    if item.get("category", "").lower() == category.lower()]
    if min_trust is not None:
        filtered = [item for item in filtered
                    if item.get("trust_score", 0) >= min_trust]

    # Paginate
    total = len(filtered)
    start = (page - 1) * limit
    end = start + limit
    page_items = filtered[start:end]

    # Serialize datetime objects
    serialized = []
    for item in page_items:
        item_copy = dict(item)
        for key in ["published_at", "last_updated"]:
            val = item_copy.get(key)
            if hasattr(val, "isoformat"):
                item_copy[key] = val.isoformat()
        serialized.append(item_copy)

    return {
        "page": page,
        "limit": limit,
        "total": total,
        "total_pages": max(1, (total + limit - 1) // limit),
        "last_refreshed": news_cache.last_refresh_iso,
        "items": serialized,
    }


# ─── Endpoint 3: Worker Status ────────────────────────────────────────────────

@router.get(
    "/status",
    summary="News Aggregation Worker Status",
    description="Returns health status, polling stats, and per-source item counts.",
)
async def get_news_status():
    """
    Monitoring endpoint for the background ingestion worker.
    """
    is_warm = news_cache.is_warm("geojson_layer")

    return {
        "worker_running": True,
        "cache_warm": is_warm,
        "last_poll": news_cache.last_refresh_iso,
        "poll_count": news_cache.poll_count,
        "item_count": news_cache.item_count,
        "poll_interval_seconds": 10,
        "temporal_window_hours": 24,
        "source_stats": news_cache.source_stats,
        "system": "NDMA DisasterLens AI — News Aggregation Subsystem v2.0",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


# ─── Endpoint 4: Force Refresh ────────────────────────────────────────────────

@router.post(
    "/refresh",
    summary="Force Immediate Re-Ingestion",
    description="Triggers an immediate ingestion cycle (async). Useful for testing.",
)
async def force_refresh(background_tasks: BackgroundTasks):
    """
    Triggers a background ingestion cycle immediately.
    Returns 202 Accepted — check /status after a few seconds.
    """
    background_tasks.add_task(run_ingestion_pipeline)
    return JSONResponse(
        {"status": "accepted", "message": "Ingestion cycle triggered. Check /api/v1/news/status."},
        status_code=202,
    )


# ─── Endpoint 5: Export API ───────────────────────────────────────────────────

@router.get("/export/stats")
async def get_export_stats():
    db = SessionLocal()
    try:
        now_utc = datetime.now(timezone.utc)
        today_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        
        total = db.query(AggregatedEvent).count()
        today = db.query(AggregatedEvent).filter(AggregatedEvent.fetched_date >= today_start).count()
        return {"total": total, "today": today}
    finally:
        db.close()

@router.get("/export")
async def export_data(format: str = Query("csv"), period: str = Query("all")):
    db = SessionLocal()
    try:
        query = db.query(AggregatedEvent)
        if period == "today":
            now_utc = datetime.now(timezone.utc)
            today_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
            query = query.filter(AggregatedEvent.fetched_date >= today_start)
            
        events = query.all()
        
        data = []
        for e in events:
            refs = []
            if e.source_refs_json:
                try:
                    refs = json.loads(e.source_refs_json)
                except:
                    pass
            refs_str = "; ".join([r.get('name', '') + f" ({r.get('url', '')})" for r in refs])
            
            data.append({
                "cluster_id": e.cluster_id,
                "title": e.title,
                "category": e.category,
                "location_name": e.location_name,
                "latitude": e.lat,
                "longitude": e.lng,
                "trust_score": e.trust_score,
                "trust_label": e.trust_label,
                "published_at": e.published_at.isoformat() if e.published_at else None,
                "fetched_date": e.fetched_date.isoformat() if e.fetched_date else None,
                "references": refs_str
            })
            
        df = pd.DataFrame(data)
        if df.empty:
            df = pd.DataFrame(columns=["cluster_id", "title", "category", "location_name", "latitude", "longitude", "trust_score", "trust_label", "published_at", "fetched_date", "references"])
            
        if format.lower() == "csv":
            stream = io.StringIO()
            df.to_csv(stream, index=False)
            stream.seek(0)
            return StreamingResponse(iter([stream.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=disaster_data_{period}.csv"})
            
        elif format.lower() == "jsonl":
            stream = io.StringIO()
            df.to_json(stream, orient="records", lines=True)
            stream.seek(0)
            return StreamingResponse(iter([stream.getvalue()]), media_type="application/jsonl", headers={"Content-Disposition": f"attachment; filename=disaster_data_{period}.jsonl"})
            
        elif format.lower() == "parquet":
            stream = io.BytesIO()
            df.to_parquet(stream, index=False)
            stream.seek(0)
            return StreamingResponse(stream, media_type="application/octet-stream", headers={"Content-Disposition": f"attachment; filename=disaster_data_{period}.parquet"})
            
        elif format.lower() == "geojson":
            features = []
            for idx, row in df.iterrows():
                features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [row.get("longitude", 0), row.get("latitude", 0)]
                    },
                    "properties": row.to_dict()
                })
            geojson = {
                "type": "FeatureCollection",
                "features": features
            }
            return JSONResponse(geojson, headers={"Content-Disposition": f"attachment; filename=disaster_data_{period}.geojson"})
            
        else:
            raise HTTPException(status_code=400, detail="Unsupported format. Use csv, jsonl, parquet, geojson")
            
    finally:
        db.close()

# ─── CORS helper ──────────────────────────────────────────────────────────────

def _cors_headers() -> dict:
    return {
        "Access-Control-Allow-Origin": "*",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "X-Data-Source": "NDMA-DisasterLens-AI",
    }
