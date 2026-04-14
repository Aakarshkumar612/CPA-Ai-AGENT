"""
Unit tests for the file-based caching layer.
"""

import time
import pytest
from unittest.mock import patch


class TestCache:
    def test_miss_returns_none(self, tmp_path):
        from utils.cache import Cache
        cache = Cache(cache_dir=str(tmp_path), ttl_hours=1)
        assert cache.get("nonexistent-key") is None

    def test_set_then_get(self, tmp_path):
        from utils.cache import Cache
        cache = Cache(cache_dir=str(tmp_path), ttl_hours=1)
        cache.set("k1", {"hello": "world"})
        result = cache.get("k1")
        assert result == {"hello": "world"}

    def test_hit_rate(self, tmp_path):
        from utils.cache import Cache
        cache = Cache(cache_dir=str(tmp_path), ttl_hours=1)
        cache.get("missing")           # miss
        cache.set("present", "value")
        cache.get("present")           # hit
        assert cache.hit_rate == 50.0

    def test_ttl_expiry(self, tmp_path):
        from utils.cache import Cache
        cache = Cache(cache_dir=str(tmp_path), ttl_hours=0.0001)  # ~360ms
        cache.set("expiring", "soon")
        time.sleep(0.5)  # wait for TTL to pass
        assert cache.get("expiring") is None

    def test_clear(self, tmp_path):
        from utils.cache import Cache
        cache = Cache(cache_dir=str(tmp_path), ttl_hours=1)
        cache.set("a", 1)
        cache.set("b", 2)
        removed = cache.clear()
        assert removed == 2
        assert cache.get("a") is None

    def test_invalidate(self, tmp_path):
        from utils.cache import Cache
        cache = Cache(cache_dir=str(tmp_path), ttl_hours=1)
        cache.set("x", 42)
        cache.invalidate("x")
        assert cache.get("x") is None

    def test_string_values(self, tmp_path):
        from utils.cache import Cache
        cache = Cache(cache_dir=str(tmp_path), ttl_hours=1)
        cache.set("text", "some markdown content")
        assert cache.get("text") == "some markdown content"


class TestDoclingCache:
    def test_get_set_roundtrip(self, tmp_path):
        from utils.cache import Cache, DoclingCache
        cache = DoclingCache(cache=Cache(cache_dir=str(tmp_path), ttl_hours=1))
        # Use a real file — create a tiny dummy
        dummy_pdf = tmp_path / "dummy.pdf"
        dummy_pdf.write_bytes(b"%PDF-1.4 test content")
        cache.set(str(dummy_pdf), "# Invoice\n## Line Items")
        result = cache.get(str(dummy_pdf))
        assert result == "# Invoice\n## Line Items"

    def test_different_files_different_keys(self, tmp_path):
        from utils.cache import Cache, DoclingCache
        cache = DoclingCache(cache=Cache(cache_dir=str(tmp_path), ttl_hours=1))
        f1 = tmp_path / "f1.pdf"
        f2 = tmp_path / "f2.pdf"
        f1.write_bytes(b"content A")
        f2.write_bytes(b"content B")
        cache.set(str(f1), "markdown A")
        cache.set(str(f2), "markdown B")
        assert cache.get(str(f1)) == "markdown A"
        assert cache.get(str(f2)) == "markdown B"


class TestLLMCache:
    def test_get_set_roundtrip(self, tmp_path):
        from utils.cache import Cache, LLMCache
        cache = LLMCache(cache=Cache(cache_dir=str(tmp_path), ttl_hours=1))
        cache.set("gpt-4", "system prompt", "user prompt", '{"result": "ok"}')
        result = cache.get("gpt-4", "system prompt", "user prompt")
        assert result == '{"result": "ok"}'

    def test_different_prompts_different_keys(self, tmp_path):
        from utils.cache import Cache, LLMCache
        cache = LLMCache(cache=Cache(cache_dir=str(tmp_path), ttl_hours=1))
        cache.set("m", "sys", "prompt A", "response A")
        cache.set("m", "sys", "prompt B", "response B")
        assert cache.get("m", "sys", "prompt A") == "response A"
        assert cache.get("m", "sys", "prompt B") == "response B"

    def test_miss_returns_none(self, tmp_path):
        from utils.cache import Cache, LLMCache
        cache = LLMCache(cache=Cache(cache_dir=str(tmp_path), ttl_hours=1))
        assert cache.get("model", "sys", "user") is None
