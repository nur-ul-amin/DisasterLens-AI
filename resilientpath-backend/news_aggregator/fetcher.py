"""
fetcher.py — Async Multi-Source HTTP Ingestion Worker
======================================================
Fetches disaster news from all configured data sources concurrently
using httpx async client. Returns raw data routed to normalizer.py.

Sources:
  1. GDACS      — GeoRSS feed (XML → feedparser)
  2. ReliefWeb  — REST API (JSON, disasters endpoint)
  3. USGS       — GeoJSON earthquake feed (past 24h, M≥4.0)
  4. GDELT      — DOC 2.0 REST API (natural disaster query)
  5. NDMA RSS   — Pakistan NDMA RSS feed
  6. ReliefWeb  — Pakistan-specific disaster updates

All fetches run concurrently via asyncio.gather().
Individual source failures are caught and logged — the pipeline
continues with remaining sources (graceful degradation).
"""

import asyncio
import logging
import time
from typing import Any, Optional

import httpx
try:
    import feedparser
except ImportError:
    feedparser = None

from .normalizer import normalize_items, NormalizedNewsItem
from .geocoder import resolve_coordinates
from .classifier import classify_hazard
from .clusterer import cluster_events, EnrichedItem, DisasterCluster
from .cache import news_cache

logger = logging.getLogger("news_aggregator.fetcher")

# ─── Source Configurations ────────────────────────────────────────────────────

SOURCES = {
    # ── Working & Verified Sources ─────────────────────────────────────────
    "GDACS": {
        # Global Disaster Alert and Coordination System — GeoRSS (reliable)
        "url": "https://www.gdacs.org/xml/rss.xml",
        "type": "rss",
        "timeout": 20,
    },
    "USGS_M25_Day": {
        # USGS Significant earthquakes M2.5+ past 24h (global, authoritative)
        "url": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson",
        "type": "json_usgs",
        "timeout": 12,
    },
    "USGS_M45_Week": {
        # USGS M4.5+ past 7 days — broader context
        "url": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson",
        "type": "json_usgs",
        "timeout": 12,
    },
    "GDACS_Floods": {
        # GDACS flood-specific feed
        "url": "https://www.gdacs.org/xml/rss_fl.xml",
        "type": "rss",
        "timeout": 15,
    },
    "GDACS_Earthquakes": {
        # GDACS earthquake-specific feed
        "url": "https://www.gdacs.org/xml/rss_eq.xml",
        "type": "rss",
        "timeout": 15,
    },
    "GDACS_Cyclones": {
        # GDACS tropical cyclone feed
        "url": "https://www.gdacs.org/xml/rss_tc.xml",
        "type": "rss",
        "timeout": 15,
    },
    "UN_OCHA_RSS": {
        # OCHA ReliefWeb humanitarian updates (public RSS — works)
        "url": "https://reliefweb.int/updates/rss.xml?primary_country=PAK",
        "type": "rss",
        "timeout": 15,
    },
    "GoogleNews_PK": {
        # Google News Pakistan - Disaster & Flood alerts
        "url": "https://news.google.com/rss/search?q=flood+OR+earthquake+OR+disaster+Pakistan&hl=en-PK&gl=PK&ceid=PK:en",
        "type": "rss",
        "timeout": 15,
    },
}

# ─── HTTP Client ──────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": "NDMA-DisasterLens-AI/2.0 (Pakistan Disaster Management System; research use)",
    "Accept": "application/json, application/xml, text/xml, */*",
}


async def _fetch_url(url: str, timeout: int = 15) -> Optional[bytes]:
    """Fetch raw bytes from a URL with timeout and error handling."""
    try:
        async with httpx.AsyncClient(
            headers=HEADERS,
            timeout=timeout,
            follow_redirects=True,
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.content
    except httpx.TimeoutException:
        logger.warning("[Fetcher] Timeout fetching: %s", url[:80])
        return None
    except httpx.HTTPStatusError as e:
        logger.warning("[Fetcher] HTTP %d for: %s", e.response.status_code, url[:80])
        return None
    except Exception as e:
        logger.warning("[Fetcher] Error fetching %s: %s", url[:80], e)
        return None


# ─── Per-Source Fetch Functions ───────────────────────────────────────────────

async def _fetch_rss(name: str, config: dict) -> list[NormalizedNewsItem]:
    """Fetch and parse an RSS/Atom feed."""
    if feedparser is None:
        logger.error("[Fetcher] feedparser not installed — cannot parse RSS")
        return []

    content = await _fetch_url(config["url"], config.get("timeout", 15))
    if not content:
        return []

    parsed = feedparser.parse(content)
    entries = parsed.get("entries", [])
    logger.info("[Fetcher][%s] RSS: %d entries fetched", name, len(entries))
    return normalize_items(name, entries)


async def _fetch_reliefweb(name: str, config: dict) -> list[NormalizedNewsItem]:
    """Fetch and parse ReliefWeb API JSON response."""
    content = await _fetch_url(config["url"], config.get("timeout", 15))
    if not content:
        return []

    try:
        import json
        data = json.loads(content)
        items = data.get("data", [])
        logger.info("[Fetcher][%s] ReliefWeb: %d items fetched", name, len(items))
        return normalize_items("ReliefWeb", items)
    except Exception as e:
        logger.warning("[Fetcher][%s] JSON parse error: %s", name, e)
        return []


async def _fetch_usgs(name: str, config: dict) -> list[NormalizedNewsItem]:
    """Fetch and parse USGS GeoJSON earthquake feed."""
    content = await _fetch_url(config["url"], config.get("timeout", 15))
    if not content:
        return []

    try:
        import json
        data = json.loads(content)
        features = data.get("features", [])
        logger.info("[Fetcher][%s] USGS: %d earthquakes fetched", name, len(features))
        return normalize_items("USGS", features)
    except Exception as e:
        logger.warning("[Fetcher][%s] JSON parse error: %s", name, e)
        return []


async def _fetch_gdelt(name: str, config: dict) -> list[NormalizedNewsItem]:
    """Fetch and parse GDELT DOC 2.0 API JSON response."""
    content = await _fetch_url(config["url"], config.get("timeout", 20))
    if not content:
        return []

    try:
        import json
        # GDELT returns plain JSON array or object
        raw = content.decode("utf-8", errors="replace")
        # GDELT sometimes returns newline-delimited or wrapped JSON
        if raw.strip().startswith("{"):
            data = json.loads(raw)
            articles = data.get("articles", [])
        else:
            articles = json.loads(raw) if raw.strip() else []

        logger.info("[Fetcher][%s] GDELT: %d articles fetched", name, len(articles))
        return normalize_items("GDELT", articles)
    except Exception as e:
        logger.warning("[Fetcher][%s] JSON parse error: %s", name, e)
        return []


from database import SessionLocal, Incident
from .social_scraper import fetch_simulated_social_media

# ─── Master Fetch Orchestrator ────────────────────────────────────────────────

SOURCE_FETCHERS = {
    "rss":              _fetch_rss,
    "json_reliefweb":   _fetch_reliefweb,
    "json_usgs":        _fetch_usgs,
    "json_gdelt":       _fetch_gdelt,
}

async def _fetch_database_reports() -> list[NormalizedNewsItem]:
    """Fetch live PWA field agent reports from the database."""
    items = []
    db = SessionLocal()
    try:
        incidents = db.query(Incident).all()
        for inc in incidents:
            hazard_cat = inc.water_depth if inc.water_depth in ["Flood", "GLOF", "Landslide", "Earthquake", "Severe Storm"] else "Flood"
            # Ensure it has a timezone-aware datetime
            from datetime import timezone
            dt = inc.created_at
            if dt and dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            
            items.append(NormalizedNewsItem(
                item_id=inc.id,
                title=inc.raw_text or f"Hazard Report ({inc.water_depth})",
                summary=inc.raw_text or "",
                url=inc.source_url or "",
                source_name="PWA Field Agent",
                source_url="http://localhost:3000",
                source_tier=2,
                base_trust_score=88,
                published_at=dt,
                raw_category=hazard_cat,
                location_text=None,
                country="Pakistan",
                raw_lat=inc.latitude,
                raw_lng=inc.longitude
            ))
        logger.info("[Fetcher] PWA Database: %d live reports fetched", len(items))
    except Exception as e:
        logger.error("[Fetcher] Database fetch error: %s", e)
    finally:
        db.close()
    return items

async def fetch_all_sources() -> list[NormalizedNewsItem]:
    """
    Concurrently fetch all configured sources.
    Returns deduplicated list of NormalizedNewsItems from the last 24 hours.
    """
    tasks = []
    source_names = []

    for name, config in SOURCES.items():
        fetcher_fn = SOURCE_FETCHERS.get(config["type"])
        if fetcher_fn:
            tasks.append(fetcher_fn(name, config))
            source_names.append(name)
        else:
            logger.warning("[Fetcher] Unknown source type '%s' for '%s'", config["type"], name)

    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_items: list[NormalizedNewsItem] = []
    seen_ids: set[str] = set()
    source_stats: dict[str, int] = {}

    for name, result in zip(source_names, results):
        if isinstance(result, Exception):
            logger.error("[Fetcher][%s] Task raised exception: %s", name, result)
            source_stats[name] = 0
            continue
        count = 0
        for item in result:
            if item.item_id not in seen_ids:
                seen_ids.add(item.item_id)
                all_items.append(item)
                count += 1
        source_stats[name] = count
        
    # Append PWA Database Reports
    db_items = await _fetch_database_reports()
    for item in db_items:
        if item.item_id not in seen_ids:
            seen_ids.add(item.item_id)
            all_items.append(item)
    source_stats["PWA_Database"] = len(db_items)
    
    # Append Simulated Social Media
    import random
    social_items = fetch_simulated_social_media(count=random.randint(2, 5))
    for item in social_items:
        if item.item_id not in seen_ids:
            seen_ids.add(item.item_id)
            all_items.append(item)
    source_stats["Social_Media"] = len(social_items)

    logger.info(
        "[Fetcher] Total unique items: %d from %d sources | %s",
        len(all_items), len(source_stats),
        " | ".join(f"{k}:{v}" for k, v in source_stats.items()),
    )
    return all_items


# ─── Full Ingestion Pipeline ──────────────────────────────────────────────────

async def run_ingestion_pipeline() -> list[DisasterCluster]:
    """
    Complete end-to-end ingestion cycle:
      1. Fetch all sources concurrently
      2. Geocode each item (Nominatim + fallback)
      3. Classify hazard category
      4. Cluster + deduplicate
      5. Write results to NewsCache

    This function is called by the background worker every 10 seconds.
    """
    start_t = time.monotonic()
    logger.info("[Pipeline] Starting ingestion cycle...")

    # Step 1: Fetch
    raw_items = await fetch_all_sources()
    if not raw_items:
        logger.warning("[Pipeline] No items fetched — all sources failed or empty")
        return []

    # Step 2 & 3: Geocode + Classify
    enriched: list[EnrichedItem] = []
    for item in raw_items:
        try:
            coords = await resolve_coordinates(
                location_text=item.location_text,
                country=item.country,
                raw_lat=item.raw_lat,
                raw_lng=item.raw_lng,
            )
            if coords is None:
                logger.debug("[Pipeline] Skipping item (no coordinates): %s", item.title[:50])
                continue

            lat, lng = coords
            category = classify_hazard(item.title, item.summary, item.raw_category)
            
            # Strict filtering: drop any item that is not classified as a known disaster
            if category == "Unknown":
                logger.debug("[Pipeline] Dropping non-disaster item: %s", item.title[:50])
                continue
                
            location_name = item.location_text or item.country or "Unknown"

            enriched.append(EnrichedItem(
                item=item,
                lat=lat,
                lng=lng,
                category=category,
                location_name=location_name,
            ))
        except Exception as e:
            logger.warning("[Pipeline] Error enriching item '%s': %s", item.title[:50], e)

    logger.info("[Pipeline] %d/%d items successfully geocoded & classified",
                len(enriched), len(raw_items))

    # Step 4: Cluster & deduplicate
    clusters = cluster_events(enriched)

    # Step 4.5: Save clusters to DB for historical export
    from database import SessionLocal, AggregatedEvent
    import json
    from datetime import datetime, timezone
    db = SessionLocal()
    try:
        now_utc = datetime.now(timezone.utc)
        for cluster in clusters:
            existing = db.query(AggregatedEvent).filter_by(cluster_id=cluster.cluster_id).first()
            if not existing:
                new_event = AggregatedEvent(
                    cluster_id=cluster.cluster_id,
                    title=cluster.title,
                    category=cluster.category,
                    location_name=cluster.location_name,
                    lat=cluster.lat,
                    lng=cluster.lng,
                    trust_score=cluster.trust_score,
                    trust_label=cluster.trust_label,
                    published_at=cluster.published_at,
                    fetched_date=now_utc,
                    source_refs_json=json.dumps(cluster.source_refs)
                )
                db.add(new_event)
        db.commit()
    except Exception as e:
        logger.error(f"[Pipeline] DB Export Error: {e}")
    finally:
        db.close()

    # Step 5: Cache results
    # Build GeoJSON FeatureCollection
    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    geojson = {
        "type": "FeatureCollection",
        "metadata": {
            "generated_at": now_iso,
            "item_count": len(clusters),
            "raw_item_count": len(raw_items),
            "temporal_window_hours": 48,
        },
        "features": [_cluster_to_geojson_feature(c) for c in clusters],
    }

    # Feed list (sorted by trust score DESC)
    feed_list = [c.dict() for c in clusters]

    await news_cache.set("geojson_layer", geojson)
    await news_cache.set("feed_list", feed_list)

    # Update cache stats
    news_cache.last_refresh = time.monotonic()
    news_cache.poll_count += 1
    news_cache.item_count = len(clusters)

    # Build per-source stats
    from collections import Counter
    src_counter = Counter()
    for item in raw_items:
        src_counter[item.source_name] += 1
    news_cache.source_stats = dict(src_counter)

    elapsed = time.monotonic() - start_t
    logger.info(
        "[Pipeline] Cycle complete: %d clusters in %.2fs (poll #%d)",
        len(clusters), elapsed, news_cache.poll_count,
    )

    return clusters


def _cluster_to_geojson_feature(cluster: DisasterCluster) -> dict:
    """Convert a DisasterCluster to a Leaflet-ready GeoJSON Feature."""
    props = cluster.dict()
    # Remove geometry fields from properties (they live in geometry block)
    props.pop("lat", None)
    props.pop("lng", None)
    # Serialize datetimes
    for key in ["published_at", "last_updated"]:
        if key in props and hasattr(props[key], "isoformat"):
            props[key] = props[key].isoformat()

    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [cluster.lng, cluster.lat],  # GeoJSON: [lng, lat]
        },
        "properties": props,
    }


# ─── Background Worker Loop ───────────────────────────────────────────────────

POLL_INTERVAL_SECONDS = 30

async def background_polling_worker():
    """
    Infinite async loop that runs the ingestion pipeline every 10 seconds.
    Designed to run as a FastAPI background task via lifespan context.
    """
    logger.info("[Worker] Background polling worker started (interval: %ds)", POLL_INTERVAL_SECONDS)
    while True:
        try:
            await run_ingestion_pipeline()
        except asyncio.CancelledError:
            logger.info("[Worker] Polling worker cancelled — shutting down")
            break
        except Exception as e:
            logger.error("[Worker] Unhandled error in pipeline: %s", e, exc_info=True)
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
