"""
scorer.py — Trust & Reliability Scoring Engine (0–100)
=======================================================
Assigns a confidence score (0–100%) to each disaster incident cluster
based on four weighted components:

  Component                   Weight   Max Points
  ─────────────────────────── ──────   ──────────
  Source Authority            40%      40
  Multi-Source Verification   35%      35
  Media Completeness          15%      15
  Temporal Freshness          10%      10
  ─────────────────────────── ──────   ──────────
  TOTAL                       100%     100

Trust labels:
  ≥ 80  → High Trust    (green)  — VERIFIED
  50–79 → Moderate      (amber)  — CROSS-CHECK
  < 50  → Unverified    (red)    — UNVERIFIED
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger("news_aggregator.scorer")

# ─── Source Authority Scores (0–100) ─────────────────────────────────────────

SOURCE_AUTHORITY_SCORES: dict[str, int] = {
    # Tier 1: Official international / UN bodies
    "GDACS":       100,
    "ReliefWeb":   95,
    "OCHA":        95,
    "UN":          95,
    # Tier 2: Government / Scientific
    "USGS":        90,
    "NDMA_RSS":    90,
    "NDMA":        90,
    "PMD":         88,  # Pakistan Met Department
    "PWA Field Agent": 88,  # Base authority calibrated to yield ~50 total score for solo reports
    "SECP":        85,
    "PDMAs":       85,
    "AIDR":        85,  # Artificial Intelligence for Disaster Response
    # Tier 3: Established media & Open Data
    "Reuters":     80,
    "AP":          80,
    "AFP":         80,
    "BBC":         78,
    "Dawn":        75,
    "GDELT":       75,  # GDELT 2.0 Global Knowledge Graph
    "ARY News":    70,
    "Geo News":    70,
    "The News":    70,
    "NewsAPI":     65,
    # Tier 4: Social Media & Unverified
    "X (Twitter)": 45,
    "Facebook":    40,
    "Instagram":   40,
    "Unknown":     30,
}


def _get_authority_score(source_name: str) -> int:
    """Look up authority score for a source. Falls back to 'Unknown'."""
    # Try exact match first, then partial match
    score = SOURCE_AUTHORITY_SCORES.get(source_name)
    if score is not None:
        return score
    # Partial match
    for key, val in SOURCE_AUTHORITY_SCORES.items():
        if key.lower() in source_name.lower():
            return val
    return SOURCE_AUTHORITY_SCORES["Unknown"]


def _compute_authority_component(source_names: list[str]) -> float:
    """
    Source Authority (max 40 pts).
    Take the HIGHEST authority among all sources in the cluster.
    Gives bonus for Tier-1 sources being present.
    """
    if not source_names:
        return 0.0
    scores = [_get_authority_score(s) for s in source_names]
    best = max(scores)
    # Normalize to 40-point scale
    return (best / 100.0) * 40.0


def _compute_verification_component(cluster_size: int) -> float:
    """
    Multi-Source Cross-Verification (max 35 pts).
    Score scales with independent source count.
      1 source  → 0 pts  (single-source claim, unverified)
      2 sources → 20 pts (basic corroboration)
      3 sources → 30 pts (strong multi-source)
      4+ sources→ 35 pts (maximum verification)
    """
    if cluster_size <= 1:
        return 0.0
    elif cluster_size == 2:
        return 20.0
    elif cluster_size == 3:
        return 30.0
    else:
        return 35.0


def _compute_completeness_component(
    image_url: Optional[str],
    video_url: Optional[str],
    location_name: Optional[str],
    lat: Optional[float],
    lng: Optional[float],
) -> float:
    """
    Media & Metadata Completeness (max 15 pts).
      +5 pts: valid image URL present
      +5 pts: structured coordinates (lat/lng) available
      +5 pts: human-readable location name present
    """
    pts = 0.0
    if image_url and image_url.startswith("http"):
        pts += 5.0
    if lat is not None and lng is not None:
        pts += 5.0
    if location_name and len(location_name) > 2:
        pts += 5.0
    return pts


def _compute_freshness_component(published_at: Optional[datetime]) -> float:
    """
    Temporal Freshness (max 10 pts).
      < 1 hour  → 10 pts
      < 6 hours → 8 pts
      < 12 hours→ 5 pts
      < 24 hours→ 2 pts
      ≥ 24 hours→ 0 pts (should not occur due to filter, but safety net)
    """
    if published_at is None:
        return 0.0
    now = datetime.now(timezone.utc)
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    age = now - published_at
    if age < timedelta(hours=1):
        return 10.0
    elif age < timedelta(hours=6):
        return 8.0
    elif age < timedelta(hours=12):
        return 5.0
    elif age < timedelta(hours=24):
        return 2.0
    return 0.0


# ─── Trust Label & Color ──────────────────────────────────────────────────────

def get_trust_label(score: float) -> str:
    if score >= 80:
        return "High Trust"
    elif score >= 50:
        return "Moderate"
    return "Unverified"


def get_trust_color(score: float) -> str:
    if score >= 80:
        return "#22c55e"   # green-500
    elif score >= 50:
        return "#f59e0b"   # amber-500
    return "#ef4444"       # red-500


def get_trust_badge_class(score: float) -> str:
    if score >= 80:
        return "trust-high"
    elif score >= 50:
        return "trust-moderate"
    return "trust-low"


# ─── Main Scoring Function ────────────────────────────────────────────────────

def score_cluster(
    source_names: list[str],
    cluster_size: int,
    image_url: Optional[str],
    video_url: Optional[str],
    location_name: Optional[str],
    lat: Optional[float],
    lng: Optional[float],
    published_at: Optional[datetime],
) -> dict:
    """
    Compute the full Trust & Reliability Score for a disaster cluster.

    Returns a dict with:
      - trust_score     (float, 0–100)
      - trust_label     (str)
      - trust_color     (str, hex)
      - trust_badge     (str, CSS class)
      - score_breakdown (dict with per-component details)
    """
    authority    = _compute_authority_component(source_names)
    verification = _compute_verification_component(cluster_size)
    completeness = _compute_completeness_component(image_url, video_url, location_name, lat, lng)
    freshness    = _compute_freshness_component(published_at)

    # Strict baseline enforcement: Solo PWA reports MUST be exactly 50/100
    if cluster_size == 1 and source_names and source_names[0] == "PWA Field Agent":
        total = 50.0
    else:
        total = round(authority + verification + completeness + freshness, 1)
        total = min(total, 100.0)  # Cap at 100

    logger.debug(
        "[Scorer] Score=%.1f | Auth=%.1f | Verif=%.1f | Complete=%.1f | Fresh=%.1f",
        total, authority, verification, completeness, freshness,
    )

    return {
        "trust_score":  total,
        "trust_label":  get_trust_label(total),
        "trust_color":  get_trust_color(total),
        "trust_badge":  get_trust_badge_class(total),
        "score_breakdown": {
            "authority":    round(authority, 1),
            "verification": round(verification, 1),
            "completeness": round(completeness, 1),
            "freshness":    round(freshness, 1),
        }
    }
