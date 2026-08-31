"""
cache.py — In-Memory TTL Cache
================================
Lightweight in-memory cache for aggregated disaster news clusters.
No Redis dependency — uses a plain Python dict with timestamps.

Design:
  - Worker refreshes every 10 seconds, so TTL is set to 30 seconds.
  - API endpoints read from cache for sub-millisecond responses.
  - Thread-safe via asyncio.Lock.
"""

import asyncio
import time
import logging
from typing import Any, Optional

logger = logging.getLogger("news_aggregator.cache")


class NewsCache:
    """
    Thread-safe in-memory cache for news aggregation results.
    Keys: arbitrary strings (e.g. "geojson_layer", "feed_list").
    Values: any Python object.
    """

    def __init__(self, default_ttl_seconds: int = 120):
        self._store: dict[str, dict] = {}
        self._lock = asyncio.Lock()
        self.default_ttl = default_ttl_seconds
        self.last_refresh: Optional[float] = None
        self.poll_count: int = 0
        self.item_count: int = 0
        self.source_stats: dict[str, int] = {}

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Store a value with an expiry timestamp."""
        async with self._lock:
            self._store[key] = {
                "value": value,
                "expires_at": time.monotonic() + (ttl or self.default_ttl),
            }
        logger.debug("[Cache] SET key='%s'", key)

    async def get(self, key: str) -> Optional[Any]:
        """Retrieve a value if it exists and has not expired."""
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if time.monotonic() > entry["expires_at"]:
                del self._store[key]
                logger.debug("[Cache] EXPIRED key='%s'", key)
                return None
            return entry["value"]

    async def invalidate(self, key: Optional[str] = None) -> None:
        """Invalidate a specific key or flush entire cache."""
        async with self._lock:
            if key:
                self._store.pop(key, None)
            else:
                self._store.clear()
        logger.debug("[Cache] INVALIDATED key='%s'", key or "ALL")

    def is_warm(self, key: str) -> bool:
        """Synchronous check — is the cache warm (non-expired) for this key?"""
        entry = self._store.get(key)
        if not entry:
            return False
        return time.monotonic() <= entry["expires_at"]

    @property
    def last_refresh_iso(self) -> Optional[str]:
        """Return last refresh time as ISO 8601 string."""
        if self.last_refresh is None:
            return None
        import datetime
        epoch = time.time() - (time.monotonic() - self.last_refresh)
        return datetime.datetime.utcfromtimestamp(epoch).strftime("%Y-%m-%dT%H:%M:%SZ")


# Singleton cache instance shared across the application
news_cache = NewsCache(default_ttl_seconds=120)
