"""Tests for disk caching."""

from core.cache import JsonCache


def test_cache_round_trip(tmp_path):
    """Values survive a cache write and read."""
    cache = JsonCache(tmp_path)
    cache.set("key", {"value": 1})
    assert cache.get("key") == {"value": 1}
