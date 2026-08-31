"""
clusterer.py — Event Deduplication & Disaster Incident Clustering
==================================================================
Groups related news items from multiple sources into unified
"Disaster Incident Clusters" using a three-gate algorithm:

  Gate 1 — SPATIAL:   Items within ~50km of each other
  Gate 2 — TEMPORAL:  Items within a 6-hour window of each other
  Gate 3 — SEMANTIC:  Title token overlap score > 0.35

Items passing all 3 gates are merged into a single DisasterCluster.
The canonical title & image come from the highest-trust source.
All source URLs are retained as secondary references.

Cluster IDs are deterministic hashes — stable across polling cycles,
enabling the frontend to detect NEW vs UPDATED clusters.
"""

import hashlib
import logging
import math
from datetime import datetime, timezone, timedelta
from typing import Optional
from pydantic import BaseModel

from .normalizer import NormalizedNewsItem, SourceRef
from .classifier import HazardCategory, get_emoji, get_color

logger = logging.getLogger("news_aggregator.clusterer")

# ─── Pydantic Output Schema ───────────────────────────────────────────────────

class DisasterCluster(BaseModel):
    """
    A unified disaster incident cluster — the primary data object
    consumed by the API and frontend.
    """
    cluster_id: str                     # Deterministic hash ID
    title: str                          # Canonical title (highest-trust source)
    summary: Optional[str] = None
    category: str                       # HazardCategory value
    category_emoji: str
    category_color: str
    lat: float
    lng: float
    location_name: str
    trust_score: float                  # 0–100 (computed by scorer.py)
    trust_label: str
    trust_color: str
    trust_badge: str
    score_breakdown: dict
    cluster_size: int                   # Number of sources grouped
    source_refs: list[dict]             # All source provenance links
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    published_at: datetime
    last_updated: datetime

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# ─── Clustering Parameters ────────────────────────────────────────────────────

GEO_RADIUS_KM   = 50.0   # Items within this radius are candidates
TEMPORAL_WINDOW = timedelta(hours=6)   # Items within 6 hours
SEMANTIC_THRESHOLD = 0.30  # Minimum token overlap score


# ─── Helper Functions ─────────────────────────────────────────────────────────

def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calculate great-circle distance in km between two WGS84 points.
    Uses the Haversine formula.
    """
    R = 6371.0  # Earth radius in km
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δφ = math.radians(lat2 - lat1)
    Δλ = math.radians(lng2 - lng1)
    a = math.sin(Δφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(Δλ / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _token_overlap(text_a: str, text_b: str) -> float:
    """
    Simple token Jaccard similarity between two text strings.
    Strips common stopwords for better signal.
    """
    STOPWORDS = {
        "the", "a", "an", "in", "of", "and", "or", "is", "are", "was",
        "were", "to", "at", "on", "for", "with", "after", "due", "kills",
        "people", "deaths", "dead", "reported", "update", "news", "hit",
        "pakistan", "flood", "earthquake", "disaster",
    }
    def tokenize(text: str) -> set[str]:
        tokens = set(text.lower().split())
        return tokens - STOPWORDS

    a_tokens = tokenize(text_a)
    b_tokens = tokenize(text_b)

    if not a_tokens or not b_tokens:
        return 0.0

    intersection = len(a_tokens & b_tokens)
    union = len(a_tokens | b_tokens)
    return intersection / union if union > 0 else 0.0


def _make_cluster_id(category: str, lat: float, lng: float, date_str: str) -> str:
    """
    Deterministic cluster ID: hash(category + geo_cell_1deg + date).
    Geo-cell rounds to 1-degree grid (~111km) so nearby events share IDs.
    """
    geo_cell = f"{int(lat)},{int(lng)}"
    raw = f"{category}::{geo_cell}::{date_str}"
    return "CL-" + hashlib.sha256(raw.encode()).hexdigest()[:12].upper()


def _centroid(items: list[tuple[float, float]]) -> tuple[float, float]:
    """Compute geographic centroid of a list of (lat, lng) tuples."""
    lats = [i[0] for i in items]
    lngs = [i[1] for i in items]
    return (sum(lats) / len(lats), sum(lngs) / len(lngs))


# ─── Enriched Item (normalizer output + geocoder + classifier) ────────────────

class EnrichedItem(BaseModel):
    """NormalizedNewsItem after geocoding and classification."""
    item: NormalizedNewsItem
    lat: float
    lng: float
    category: str
    location_name: str

    class Config:
        arbitrary_types_allowed = True


# ─── Main Clustering Algorithm ────────────────────────────────────────────────

def cluster_events(enriched_items: list[EnrichedItem]) -> list[DisasterCluster]:
    """
    Three-gate clustering algorithm:

    1. Sort items by published_at DESC (newest first)
    2. For each unassigned item, scan all later unassigned items:
       - Gate 1 (Spatial): distance < GEO_RADIUS_KM
       - Gate 2 (Temporal): |time_delta| < TEMPORAL_WINDOW
       - Gate 3 (Semantic): token_overlap > SEMANTIC_THRESHOLD OR same category
    3. Group passing items into one cluster
    4. Assign cluster representative: highest base_trust_score item

    Returns: list[DisasterCluster] sorted by trust_score DESC
    """
    if not enriched_items:
        return []

    # Sort newest first
    sorted_items = sorted(enriched_items, key=lambda x: x.item.published_at, reverse=True)
    assigned = [False] * len(sorted_items)
    clusters_raw: list[list[EnrichedItem]] = []

    for i, anchor in enumerate(sorted_items):
        if assigned[i]:
            continue

        group = [anchor]
        assigned[i] = True

        for j in range(i + 1, len(sorted_items)):
            if assigned[j]:
                continue
            candidate = sorted_items[j]

            # Gate 1: Spatial proximity
            dist_km = _haversine_km(anchor.lat, anchor.lng, candidate.lat, candidate.lng)
            if dist_km > GEO_RADIUS_KM:
                continue

            # Gate 2: Temporal window
            t_anchor = anchor.item.published_at
            t_cand   = candidate.item.published_at
            if t_anchor.tzinfo is None:
                t_anchor = t_anchor.replace(tzinfo=timezone.utc)
            if t_cand.tzinfo is None:
                t_cand = t_cand.replace(tzinfo=timezone.utc)
            if abs(t_anchor - t_cand) > TEMPORAL_WINDOW:
                continue

            # Gate 3: Semantic or same category
            same_category = (anchor.category == candidate.category and
                             anchor.category != HazardCategory.UNKNOWN)
            overlap = _token_overlap(anchor.item.title, candidate.item.title)
            if not same_category and overlap < SEMANTIC_THRESHOLD:
                continue

            group.append(candidate)
            assigned[j] = True

        clusters_raw.append(group)

    # Build DisasterCluster objects
    output_clusters: list[DisasterCluster] = []

    for group in clusters_raw:
        # Pick canonical item: highest base_trust_score
        canonical = max(group, key=lambda x: x.item.base_trust_score)

        # Compute geographic centroid
        all_coords = [(e.lat, e.lng) for e in group]
        c_lat, c_lng = _centroid(all_coords)

        # Pick the most common category (majority vote)
        from collections import Counter
        cat_counter = Counter(e.category for e in group)
        category = cat_counter.most_common(1)[0][0]

        # Use canonical item's published_at as cluster time
        published_at = canonical.item.published_at
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)

        date_str = published_at.strftime("%Y%m%d")
        cluster_id = _make_cluster_id(category, c_lat, c_lng, date_str)

        # Collect source refs
        source_refs = []
        seen_urls = set()
        for e in sorted(group, key=lambda x: x.item.base_trust_score, reverse=True):
            url = e.item.source_url
            if url not in seen_urls:
                seen_urls.add(url)
                source_refs.append({
                    "name": e.item.source_name,
                    "url": url,
                    "tier": e.item.source_tier,
                    "base_trust": e.item.base_trust_score,
                })

        # Pick best image and video
        image_url = next((e.item.image_url for e in group
                          if e.item.image_url and e.item.image_url.startswith("http")), None)
        video_url = next((e.item.video_url for e in group
                          if e.item.video_url and e.item.video_url.startswith("http")), None)

        # Location name from canonical item or best available
        location_name = (canonical.location_name or
                         next((e.location_name for e in group if e.location_name), "Unknown Location"))

        # Compute trust score (placeholder values — will be patched by routes/news.py
        # after scorer.py is called with full data)
        from .scorer import score_cluster
        scoring = score_cluster(
            source_names=[e.item.source_name for e in group],
            cluster_size=len(group),
            image_url=image_url,
            video_url=video_url,
            location_name=location_name,
            lat=c_lat,
            lng=c_lng,
            published_at=published_at,
        )

        cluster = DisasterCluster(
            cluster_id=cluster_id,
            title=canonical.item.title,
            summary=canonical.item.summary,
            category=category,
            category_emoji=get_emoji(category),
            category_color=get_color(category),
            lat=round(c_lat, 6),
            lng=round(c_lng, 6),
            location_name=location_name,
            trust_score=scoring["trust_score"],
            trust_label=scoring["trust_label"],
            trust_color=scoring["trust_color"],
            trust_badge=scoring["trust_badge"],
            score_breakdown=scoring["score_breakdown"],
            cluster_size=len(group),
            source_refs=source_refs,
            image_url=image_url,
            video_url=video_url,
            published_at=published_at,
            last_updated=datetime.now(timezone.utc),
        )
        output_clusters.append(cluster)

    # Sort by trust score DESC, then by published_at DESC
    output_clusters.sort(key=lambda c: (c.trust_score, c.published_at.timestamp()), reverse=True)

    logger.info(
        "[Clusterer] %d items → %d clusters (%.1f%% dedup rate)",
        len(enriched_items),
        len(output_clusters),
        (1 - len(output_clusters) / max(len(enriched_items), 1)) * 100,
    )
    return output_clusters
