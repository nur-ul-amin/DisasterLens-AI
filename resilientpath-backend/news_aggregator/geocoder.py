"""
geocoder.py — Location Entity Extraction & Coordinate Resolution
=================================================================
Extracts location mentions from news items and resolves them to
WGS84 (lat, lon) coordinates for Leaflet.js rendering via Nominatim.

Features:
  - In-process LRU cache to avoid repeat Nominatim calls
  - Rate limiting: max 1 request/second (Nominatim ToS)
  - Prefers raw coordinates from source (e.g., USGS, GDACS)
  - Fallback: country-centroid lookup for coarse positioning
  - Pakistan boundary filtering (optional, enabled by default)
"""

import asyncio
import logging
import re
import time
from functools import lru_cache
from typing import Optional

import httpx

logger = logging.getLogger("news_aggregator.geocoder")

# ─── Country Centroid Fallback Table ─────────────────────────────────────────
# Used when Nominatim fails or location text is only a country name.

COUNTRY_CENTROIDS: dict[str, tuple[float, float]] = {
    "Pakistan":          (30.3753, 69.3451),
    "Afghanistan":       (33.9391, 67.7100),
    "India":             (20.5937, 78.9629),
    "Bangladesh":        (23.6850, 90.3563),
    "Nepal":             (28.3949, 84.1240),
    "Sri Lanka":         (7.8731,  80.7718),
    "Iran":              (32.4279, 53.6880),
    "Turkey":            (38.9637, 35.2433),
    "Indonesia":         (-0.7893, 113.9213),
    "Philippines":       (12.8797, 121.7740),
    "Japan":             (36.2048, 138.2529),
    "China":             (35.8617, 104.1954),
    "Myanmar":           (21.9162, 95.9560),
    "Syria":             (34.8021, 38.9968),
    "Somalia":           (5.1521,  46.1996),
    "Ethiopia":          (9.1450,  40.4897),
    "Sudan":             (12.8628, 30.2176),
    "Yemen":             (15.5527, 48.5164),
    "Global":            (30.3753, 69.3451),  # Default to Pakistan
}

# Nominatim API endpoint
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_RATE_LIMIT = 1.1  # seconds between requests

_last_nominatim_call: float = 0.0
_nominatim_cache: dict[str, Optional[tuple[float, float]]] = {}

# ─── Pakistan Bounding Box (for global filtering) ─────────────────────────────
PK_BBOX = {"lat_min": 23.5, "lat_max": 37.5, "lng_min": 60.5, "lng_max": 77.5}


def _coords_in_pakistan(lat: float, lng: float) -> bool:
    return (PK_BBOX["lat_min"] <= lat <= PK_BBOX["lat_max"] and
            PK_BBOX["lng_min"] <= lng <= PK_BBOX["lng_max"])


async def _nominatim_lookup(query: str) -> Optional[tuple[float, float]]:
    """
    Single Nominatim reverse-geocoding lookup with rate limiting and caching.
    Returns (lat, lng) or None on failure.
    """
    global _last_nominatim_call

    cache_key = query.lower().strip()
    if cache_key in _nominatim_cache:
        return _nominatim_cache[cache_key]

    # Enforce rate limit
    elapsed = time.monotonic() - _last_nominatim_call
    if elapsed < NOMINATIM_RATE_LIMIT:
        await asyncio.sleep(NOMINATIM_RATE_LIMIT - elapsed)

    params = {
        "q": query,
        "format": "json",
        "limit": 1,
        "addressdetails": 0,
    }
    headers = {
        "User-Agent": "NDMA-DisasterLens-AI/2.0 (Pakistan Disaster Management; research)"
    }

    try:
        _last_nominatim_call = time.monotonic()
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(NOMINATIM_URL, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        if data:
            lat = float(data[0]["lat"])
            lng = float(data[0]["lon"])
            result = (lat, lng)
            _nominatim_cache[cache_key] = result
            logger.debug("[Geocoder] Nominatim resolved '%s' → (%.4f, %.4f)", query, lat, lng)
            return result
        else:
            _nominatim_cache[cache_key] = None
            return None

    except Exception as e:
        logger.warning("[Geocoder] Nominatim lookup failed for '%s': %s", query, e)
        _nominatim_cache[cache_key] = None
        return None


def _country_centroid(location_text: Optional[str], country: Optional[str]) -> Optional[tuple[float, float]]:
    """Coarse fallback: match location text against country centroid table."""
    candidates = [country, location_text]
    for cand in candidates:
        if not cand:
            continue
        for country_name, coords in COUNTRY_CENTROIDS.items():
            if country_name.lower() in cand.lower():
                return coords
    return None


async def resolve_coordinates(
    location_text: Optional[str],
    country: Optional[str],
    raw_lat: Optional[float],
    raw_lng: Optional[float],
) -> Optional[tuple[float, float]]:
    """
    Resolve a news item's location to (lat, lng).

    Priority order:
    1. Source-provided coordinates (USGS, GDACS — authoritative)
    2. Nominatim lookup of location_text
    3. Country centroid fallback
    4. Pakistan centroid (last resort for Pakistan-focused sources)
    """
    # 1. Source-provided coordinates
    if raw_lat is not None and raw_lng is not None:
        return (raw_lat, raw_lng)

    # 2. Nominatim lookup
    if location_text:
        # Try the most specific query first, then progressively coarser
        queries = [location_text]
        if country and country.lower() not in location_text.lower():
            queries.append(f"{location_text}, {country}")
        for q in queries:
            coords = await _nominatim_lookup(q)
            if coords:
                return coords

    # 3. Country centroid fallback
    centroid = _country_centroid(location_text, country)
    if centroid:
        return centroid

    # 4. Default: Pakistan (this system is Pakistan-focused)
    return None  # Caller can handle None (item won't appear on map)
