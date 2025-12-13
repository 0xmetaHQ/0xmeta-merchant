import redis
import json
from typing import Optional, Any
from app.core.config import settings
from loguru import logger


class RedisClient:
    def __init__(self):
        self.client: Optional[redis.Redis] = None
        self.ttl = settings.REDIS_TTL
    
    async def connect(self):
        """Initialize Redis connection"""
        try:
            self.client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=5
            )
            self.client.ping()
            logger.info("✓ Redis connection established successfully")
            return True
        except Exception as e:
            logger.error(f"✗ Redis connection failed: {str(e)}")
            return False
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            if not self.client:
                return None
            value = self.client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Redis GET error for key {key}: {str(e)}")
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache with TTL"""
        try:
            if not self.client:
                return False
            serialized = json.dumps(value, default=str)
            expire_time = ttl or self.ttl
            self.client.setex(key, expire_time, serialized)
            return True
        except Exception as e:
            logger.error(f"Redis SET error for key {key}: {str(e)}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            if not self.client:
                return False
            self.client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis DELETE error for key {key}: {str(e)}")
            return False
    
    def clear_pattern(self, pattern: str) -> bool:
        """Clear all keys matching pattern"""
        try:
            if not self.client:
                return False
            keys = self.client.keys(pattern)
            if keys:
                self.client.delete(*keys)
            return True
        except Exception as e:
            logger.error(f"Redis CLEAR error for pattern {pattern}: {str(e)}")
            return False


redis_client = RedisClient()