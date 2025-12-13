"""
Cache module - Redis caching layer
"""

from app.cache.redis_client import redis_client

__all__ = ["redis_client"]