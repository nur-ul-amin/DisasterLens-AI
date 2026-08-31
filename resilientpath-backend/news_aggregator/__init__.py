"""
news_aggregator — Live Disaster News Aggregation Subsystem
==========================================================
NDMA DisasterLens AI | Multi-Hazard Platform
Pakistan National Disaster Management Authority

Submodule layout:
  cache.py      — In-memory TTL cache (no Redis dependency)
  fetcher.py    — Async multi-source HTTP ingestion worker
  normalizer.py — Heterogeneous payload → NormalizedNewsItem schema
  geocoder.py   — Location text → WGS84 coordinates (Nominatim)
  classifier.py — Keyword-based multi-hazard category classifier
  clusterer.py  — Geo+temporal+semantic event deduplication & clustering
  scorer.py     — Trust & Reliability Scoring Engine (0–100)
"""

from .cache import NewsCache
from .fetcher import fetch_all_sources
from .normalizer import normalize_items
from .geocoder import resolve_coordinates
from .classifier import classify_hazard
from .clusterer import cluster_events
from .scorer import score_cluster

__all__ = [
    "NewsCache",
    "fetch_all_sources",
    "normalize_items",
    "resolve_coordinates",
    "classify_hazard",
    "cluster_events",
    "score_cluster",
]
