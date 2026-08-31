"""
normalizer.py — Payload Normalizer & 24-Hour Temporal Filter
=============================================================
Converts heterogeneous source payloads (GDACS XML, ReliefWeb JSON,
USGS GeoJSON, GDELT JSON, RSS Atom) into a unified NormalizedNewsItem
Pydantic schema and applies the strict 24-hour temporal window filter.
"""

import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, Any
from pydantic import BaseModel, validator, HttpUrl

logger = logging.getLogger("news_aggregator.normalizer")

# ─── Pydantic Schemas ────────────────────────────────────────────────────────

class SourceRef(BaseModel):
    """A provenance reference to one news source."""
    name: str
    url: str
    tier: int           # 1=official/UN, 2=gov/scientific, 3=media
    base_trust: int     # 0-100 authority score for this source


class NormalizedNewsItem(BaseModel):
    """
    Unified schema for a single disaster news item after normalization.
    All fields are populated regardless of source format.
    """
    item_id: str                        # Unique hash for deduplication
    source_name: str
    source_tier: int
    base_trust_score: int               # Authority baseline (0-100)
    title: str
    summary: Optional[str] = None
    source_url: str
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    published_at: datetime
    location_text: Optional[str] = None
    country: Optional[str] = None
    raw_lat: Optional[float] = None     # Lat from source payload (if provided)
    raw_lng: Optional[float] = None     # Lng from source payload (if provided)
    raw_category: Optional[str] = None  # Source-native category label

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# ─── Source Authority Registry ────────────────────────────────────────────────

SOURCE_AUTHORITY: dict[str, dict] = {
    "GDACS":       {"tier": 1, "trust": 100},
    "ReliefWeb":   {"tier": 1, "trust": 95},
    "USGS":        {"tier": 2, "trust": 90},
    "NDMA_RSS":    {"tier": 2, "trust": 90},
    "GDELT":       {"tier": 3, "trust": 60},
    "NewsAPI":     {"tier": 3, "trust": 65},
    "Unknown":     {"tier": 3, "trust": 30},
}


def _get_source_meta(source_name: str) -> dict:
    return SOURCE_AUTHORITY.get(source_name, SOURCE_AUTHORITY["Unknown"])


def _is_within_24h(published_at: Optional[datetime]) -> bool:
    """Strict 2-day temporal window filter."""
    if published_at is None:
        return False
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=2)
    # Ensure dt is timezone-aware
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    return published_at >= cutoff


def _extract_image(entry: dict) -> Optional[str]:
    """Try multiple known fields to extract image URL."""
    candidates = [
        entry.get("image_url"),
        entry.get("thumbnail"),
        entry.get("enclosure_url"),
        entry.get("media_content", [{}])[0].get("url") if entry.get("media_content") else None,
    ]
    for c in candidates:
        if c and isinstance(c, str) and c.startswith("http"):
            return c
    return None


def _extract_video(summary: Optional[str]) -> Optional[str]:
    """Detect YouTube embed URLs or direct MP4 links from summary text."""
    if not summary:
        return None
    yt_pattern = r"(https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+|https?://youtu\.be/[\w-]+)"
    mp4_pattern = r"(https?://[^\s\"']+\.mp4)"
    for pat in [yt_pattern, mp4_pattern]:
        m = re.search(pat, summary)
        if m:
            return m.group(1)
    return None


def _make_item_id(source_name: str, url: str, published_at: Optional[datetime]) -> str:
    """Deterministic ID for deduplication across polling cycles."""
    import hashlib
    ts = published_at.isoformat() if published_at else ""
    raw = f"{source_name}::{url}::{ts}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ─── Per-Source Normalizers ───────────────────────────────────────────────────

def normalize_gdacs(raw_items: list[dict]) -> list[NormalizedNewsItem]:
    """Normalize GDACS GeoRSS feed entries."""
    meta = _get_source_meta("GDACS")
    results = []
    for entry in raw_items:
        try:
            published_str = entry.get("published") or entry.get("updated")
            try:
                from dateutil import parser as dp
                published_at = dp.parse(published_str) if published_str else None
            except Exception:
                published_at = None

            if not _is_within_24h(published_at):
                continue

            url = entry.get("link", "")
            item = NormalizedNewsItem(
                item_id=_make_item_id("GDACS", url, published_at),
                source_name="GDACS",
                source_tier=meta["tier"],
                base_trust_score=meta["trust"],
                title=entry.get("title", "GDACS Alert"),
                summary=entry.get("summary", ""),
                source_url=url,
                image_url=_extract_image(entry),
                video_url=_extract_video(entry.get("summary")),
                published_at=published_at,
                location_text=entry.get("gdacs_country") or entry.get("where", {}).get("value"),
                country=entry.get("gdacs_country"),
                raw_lat=entry.get("geo_lat") or entry.get("where", {}).get("lat"),
                raw_lng=entry.get("geo_long") or entry.get("where", {}).get("lng"),
                raw_category=entry.get("gdacs_eventtype"),
            )
            results.append(item)
        except Exception as e:
            logger.warning("[Normalizer][GDACS] Skipping entry: %s", e)
    return results


def normalize_reliefweb(raw_items: list[dict]) -> list[NormalizedNewsItem]:
    """Normalize ReliefWeb API JSON response items."""
    meta = _get_source_meta("ReliefWeb")
    results = []
    for item_data in raw_items:
        try:
            fields = item_data.get("fields", {})
            published_str = fields.get("date", {}).get("created") or fields.get("date", {}).get("original")
            try:
                from dateutil import parser as dp
                published_at = dp.parse(published_str) if published_str else None
            except Exception:
                published_at = None

            if not _is_within_24h(published_at):
                continue

            url = fields.get("url") or f"https://reliefweb.int/node/{item_data.get('id', '')}"
            country_list = fields.get("country", [])
            country = country_list[0].get("name") if country_list else None
            location_parts = [country] if country else []
            primary_country = fields.get("primary_country", {}).get("name")
            if primary_country and primary_country not in location_parts:
                location_parts.insert(0, primary_country)

            # Extract image from file field
            image_url = None
            for f in fields.get("file", []):
                if f.get("mimetype", "").startswith("image/"):
                    image_url = f.get("url")
                    break

            item = NormalizedNewsItem(
                item_id=_make_item_id("ReliefWeb", url, published_at),
                source_name="ReliefWeb",
                source_tier=meta["tier"],
                base_trust_score=meta["trust"],
                title=fields.get("title", "ReliefWeb Update"),
                summary=fields.get("body-html") or fields.get("body"),
                source_url=url,
                image_url=image_url,
                video_url=_extract_video(fields.get("body")),
                published_at=published_at,
                location_text=", ".join(location_parts) if location_parts else None,
                country=primary_country or country,
                raw_category=fields.get("disaster_type", [{}])[0].get("name") if fields.get("disaster_type") else None,
            )
            results.append(item)
        except Exception as e:
            logger.warning("[Normalizer][ReliefWeb] Skipping item: %s", e)
    return results


def normalize_usgs(raw_features: list[dict]) -> list[NormalizedNewsItem]:
    """Normalize USGS GeoJSON earthquake features."""
    meta = _get_source_meta("USGS")
    results = []
    for feature in raw_features:
        try:
            props = feature.get("properties", {})
            geom = feature.get("geometry", {})
            coords = geom.get("coordinates", [None, None, None])

            ts_ms = props.get("time")
            published_at = None
            if ts_ms:
                published_at = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)

            if not _is_within_24h(published_at):
                continue

            url = props.get("url") or props.get("detail", "")
            mag = props.get("mag", "?")
            place = props.get("place", "Unknown location")

            item = NormalizedNewsItem(
                item_id=_make_item_id("USGS", url, published_at),
                source_name="USGS",
                source_tier=meta["tier"],
                base_trust_score=meta["trust"],
                title=f"M{mag} Earthquake — {place}",
                summary=f"Magnitude {mag} earthquake detected near {place}. Depth: {coords[2] if len(coords) > 2 else '?'}km.",
                source_url=url,
                image_url=None,
                published_at=published_at,
                location_text=place,
                raw_lat=coords[1] if len(coords) > 1 else None,
                raw_lng=coords[0] if coords else None,
                raw_category="earthquake",
            )
            results.append(item)
        except Exception as e:
            logger.warning("[Normalizer][USGS] Skipping feature: %s", e)
    return results


def normalize_gdelt(raw_items: list[dict]) -> list[NormalizedNewsItem]:
    """Normalize GDELT DOC API article results."""
    meta = _get_source_meta("GDELT")
    results = []
    for article in raw_items:
        try:
            published_str = article.get("seendate", "")
            try:
                # GDELT format: YYYYMMDDTHHMMSSZ
                from dateutil import parser as dp
                published_at = dp.parse(published_str) if published_str else None
            except Exception:
                published_at = None

            if not _is_within_24h(published_at):
                continue

            url = article.get("url", "")
            item = NormalizedNewsItem(
                item_id=_make_item_id("GDELT", url, published_at),
                source_name="GDELT",
                source_tier=meta["tier"],
                base_trust_score=meta["trust"],
                title=article.get("title", "Disaster Event"),
                summary=article.get("seendate"),
                source_url=url,
                image_url=article.get("socialimage"),
                published_at=published_at,
                location_text=article.get("sourcecountry"),
                country=article.get("sourcecountry"),
                raw_category=None,
            )
            results.append(item)
        except Exception as e:
            logger.warning("[Normalizer][GDELT] Skipping article: %s", e)
    return results


def normalize_rss(raw_items: list[dict], source_name: str = "NDMA_RSS") -> list[NormalizedNewsItem]:
    """Normalize generic RSS/Atom feed entries (feedparser format)."""
    meta = _get_source_meta(source_name)
    results = []
    for entry in raw_items:
        try:
            import time as time_mod
            published_at = None
            time_struct = entry.get("published_parsed") or entry.get("updated_parsed")
            if time_struct:
                published_at = datetime(*time_struct[:6], tzinfo=timezone.utc)

            if not _is_within_24h(published_at):
                continue

            url = entry.get("link", "")
            summary_raw = entry.get("summary", "") or ""
            # Strip HTML tags from summary
            summary_clean = re.sub(r"<[^>]+>", " ", summary_raw).strip()

            item = NormalizedNewsItem(
                item_id=_make_item_id(source_name, url, published_at),
                source_name=source_name,
                source_tier=meta["tier"],
                base_trust_score=meta["trust"],
                title=entry.get("title", "Disaster Update"),
                summary=summary_clean[:1000],
                source_url=url,
                image_url=_extract_image(entry),
                video_url=_extract_video(summary_raw),
                published_at=published_at,
                location_text=entry.get("tags", [{}])[0].get("term") if entry.get("tags") else None,
            )
            results.append(item)
        except Exception as e:
            logger.warning("[Normalizer][RSS:%s] Skipping entry: %s", source_name, e)
    return results


def normalize_items(source_name: str, raw_data: Any) -> list[NormalizedNewsItem]:
    """
    Central dispatch: route raw data to the correct per-source normalizer.
    Returns a list of NormalizedNewsItem objects passing the 24-hour filter.
    """
    normalizers = {
        "GDACS":    lambda d: normalize_gdacs(d),
        "ReliefWeb": lambda d: normalize_reliefweb(d),
        "USGS":     lambda d: normalize_usgs(d),
        "GDELT":    lambda d: normalize_gdelt(d),
    }

    if source_name in normalizers:
        return normalizers[source_name](raw_data)

    # Default: treat as RSS
    return normalize_rss(raw_data, source_name=source_name)
