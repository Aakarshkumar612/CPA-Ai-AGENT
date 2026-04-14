"""
Caching Layer — Speed up pipeline by avoiding redundant work.

What this does:
1. Caches Docling markdown extraction (PDFs don't change, no need to re-parse)
2. Caches LLM responses (same PDF + same prompt = same response)
3. Caches rate lookups (in-memory, routes don't change during a run)

Why caching matters:
- Docling parsing takes 3-5 seconds per PDF
- Groq API calls cost money (even if cheap) and have rate limits
- If you re-run the pipeline on the same 100 PDFs, caching saves ~90% of work
- For assessment demos, re-running is instant after the first pass

Cache strategy:
- File-based JSON cache (persists between runs)
- Cache key = SHA256 hash of input (content-based invalidation)
- TTL (time-to-live) to auto-expire stale cache entries
- Cache stats logged (hit rate, miss rate)
"""

import json
import hashlib
import logging
from pathlib import Path
from typing import Optional, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

CACHE_DIR = Path(".cache")


class Cache:
    """
    File-based JSON cache with TTL support.
    
    Usage:
        cache = Cache()
        
        # Check cache first
        cached = cache.get("some_key")
        if cached is not None:
            return cached  # Cache hit!
        
        # Expensive operation
        result = expensive_operation()
        
        # Store in cache
        cache.set("some_key", result)
    
    Why file-based?
    - No Redis or external service needed
    - Survives process restarts
    - Easy to inspect (it's just JSON files)
    - Perfect for CLI tools and batch processing
    """

    def __init__(
        self,
        cache_dir: str = str(CACHE_DIR),
        ttl_hours: Optional[float] = None,
    ):
        from utils.settings import settings as _settings
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        resolved_ttl = ttl_hours if ttl_hours is not None else _settings.CACHE_TTL_HOURS
        self.ttl = timedelta(hours=resolved_ttl)
        self.hits = 0
        self.misses = 0
        logger.info("Cache initialized: %s (TTL=%.1f hours)", cache_dir, resolved_ttl)

    @staticmethod
    def hash_key(data: str) -> str:
        """
        Create a SHA256 hash of input data for use as cache key.
        
        Why SHA256?
        - Fixed length (64 chars) regardless of input size
        - Collision-resistant (different inputs → different keys)
        - Fast to compute
        - Safe for use as filename
        """
        return hashlib.sha256(data.encode("utf-8")).hexdigest()

    def _get_cache_path(self, key: str) -> Path:
        """Get the file path for a cache entry."""
        return self.cache_dir / f"{key}.json"

    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve a value from cache.
        
        Returns:
            Cached value if found and not expired, None otherwise
        """
        cache_path = self._get_cache_path(key)
        
        if not cache_path.exists():
            self.misses += 1
            return None

        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                entry = json.load(f)

            # Check TTL
            stored_at = datetime.fromisoformat(entry["_cached_at"])
            if datetime.now() - stored_at > self.ttl:
                # Expired — delete the cache file
                cache_path.unlink()
                logger.debug("Cache expired: %s", key[:16])
                self.misses += 1
                return None

            self.hits += 1
            logger.debug("Cache hit: %s", key[:16])
            return entry["_value"]

        except (json.JSONDecodeError, IOError, KeyError) as e:
            logger.debug("Cache read error: %s", e)
            self.misses += 1
            return None

    def set(self, key: str, value: Any) -> None:
        """
        Store a value in cache.
        
        Args:
            key: Cache key (usually a hash)
            value: Any JSON-serializable value to cache
        """
        cache_path = self._get_cache_path(key)

        entry = {
            "_cached_at": datetime.now().isoformat(),
            "_value": value,
        }

        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(entry, f, ensure_ascii=False, indent=2)
            logger.debug("Cache set: %s", key[:16])
        except IOError as e:
            logger.warning("Failed to write cache for %s: %s", key[:16], e)

    def invalidate(self, key: str) -> None:
        """Remove a specific cache entry."""
        cache_path = self._get_cache_path(key)
        if cache_path.exists():
            cache_path.unlink()
            logger.debug("Cache invalidated: %s", key[:16])

    def clear(self) -> int:
        """
        Clear all cache entries.
        
        Returns:
            Number of entries cleared
        """
        count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()
            count += 1
        logger.info("Cache cleared: %d entries removed", count)
        self.hits = 0
        self.misses = 0
        return count

    @property
    def hit_rate(self) -> float:
        """Return cache hit rate as a percentage (0-100)."""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return round((self.hits / total) * 100, 1)

    def log_stats(self) -> None:
        """Log cache performance statistics."""
        logger.info(
            "Cache stats: %d hits, %d misses, %.1f%% hit rate",
            self.hits,
            self.misses,
            self.hit_rate,
        )


class DoclingCache:
    """
    Specialized cache for Docling PDF-to-markdown conversion.
    
    Cache key = SHA256 hash of the PDF file content.
    This means if even one byte of the PDF changes, we get a cache miss (correct behavior).
    """

    def __init__(self, cache: Optional[Cache] = None):
        self.cache = cache or Cache()

    def get(self, pdf_path: str) -> Optional[str]:
        """Get cached markdown for a PDF file."""
        file_hash = self._hash_file(pdf_path)
        return self.cache.get(file_hash)

    def set(self, pdf_path: str, markdown: str) -> None:
        """Cache markdown output for a PDF file."""
        file_hash = self._hash_file(pdf_path)
        self.cache.set(file_hash, markdown)

    @staticmethod
    def _hash_file(file_path: str) -> str:
        """Create SHA256 hash of a file's content."""
        sha = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha.update(chunk)
        return f"docling_{sha.hexdigest()}"


class LLMCache:
    """
    Specialized cache for Groq LLM responses.
    
    Cache key = SHA256 hash of (model + system_prompt + user_prompt).
    Same model + same prompts = same response (for deterministic temperature=0.1).
    """

    def __init__(self, cache: Optional[Cache] = None):
        self.cache = cache or Cache()

    def get(self, model: str, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Get cached LLM response."""
        key = self._make_key(model, system_prompt, user_prompt)
        return self.cache.get(key)

    def set(self, model: str, system_prompt: str, user_prompt: str, response: str) -> None:
        """Cache LLM response."""
        key = self._make_key(model, system_prompt, user_prompt)
        self.cache.set(key, response)

    @staticmethod
    def _make_key(model: str, system_prompt: str, user_prompt: str) -> str:
        """Create cache key from LLM call parameters."""
        combined = f"llm_{model}_{system_prompt}_{user_prompt}"
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()


# ── Global cache instance ──
# Single instance shared across all agents
_global_cache: Optional[Cache] = None

def get_cache() -> Cache:
    """Get or create the global cache instance."""
    global _global_cache
    if _global_cache is None:
        _global_cache = Cache()
    return _global_cache

def get_docling_cache() -> DoclingCache:
    """Get the Docling cache."""
    return DoclingCache(cache=get_cache())

def get_llm_cache() -> LLMCache:
    """Get the LLM cache."""
    return LLMCache(cache=get_cache())
