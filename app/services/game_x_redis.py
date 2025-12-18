"""
Redis-based caching layer for GameX Twitter data
Persistent caching across app restarts
"""

import json
from typing import List, Dict, Any, Optional
from datetime import timedelta
import redis.asyncio as redis
from loguru import logger

from app.core.config import settings


class TwitterCacheService:
    """Redis-based caching for Twitter data"""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.cache_ttl = 900  # 15 minutes in seconds
        self.user_ids_ttl = 86400  # 24 hours for user IDs
        
        # Cache key prefixes
        self.TWEETS_PREFIX = "twitter:tweets:"
        self.USER_ID_PREFIX = "twitter:user_id:"
        self.BATCH_PREFIX = "twitter:batch:"
        self.LAST_FETCH_PREFIX = "twitter:last_fetch:"
    
    async def initialize(self):
        """Initialize Redis connection"""
        try:
            self.redis_client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
            await self.redis_client.ping()
            logger.info("✅ Redis cache initialized for Twitter data")
            return True
        except Exception as e:
            logger.error(f"❌ Redis initialization failed: {e}")
            return False
    
    async def get_user_id(self, username: str) -> Optional[str]:
        """Get cached user ID"""
        try:
            key = f"{self.USER_ID_PREFIX}{username.lower()}"
            user_id = await self.redis_client.get(key)
            if user_id:
                logger.debug(f"💾 Cache hit for user ID: @{username}")
            return user_id
        except Exception as e:
            logger.error(f"Error getting user ID from cache: {e}")
            return None
    
    async def set_user_id(self, username: str, user_id: str):
        """Cache user ID (long TTL)"""
        try:
            key = f"{self.USER_ID_PREFIX}{username.lower()}"
            await self.redis_client.setex(
                key,
                self.user_ids_ttl,
                user_id
            )
            logger.debug(f"✅ Cached user ID for @{username}")
        except Exception as e:
            logger.error(f"Error caching user ID: {e}")
    
    async def get_user_tweets(self, username: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached tweets for a user"""
        try:
            key = f"{self.TWEETS_PREFIX}{username.lower()}"
            tweets_json = await self.redis_client.get(key)
            if tweets_json:
                logger.debug(f"💾 Cache hit for @{username} tweets")
                return json.loads(tweets_json)
            return None
        except Exception as e:
            logger.error(f"Error getting tweets from cache: {e}")
            return None
    
    async def set_user_tweets(self, username: str, tweets: List[Dict[str, Any]]):
        """Cache tweets for a user"""
        try:
            key = f"{self.TWEETS_PREFIX}{username.lower()}"
            tweets_json = json.dumps(tweets)
            await self.redis_client.setex(
                key,
                self.cache_ttl,
                tweets_json
            )
            logger.debug(f"✅ Cached {len(tweets)} tweets for @{username}")
        except Exception as e:
            logger.error(f"Error caching tweets: {e}")
    
    async def get_batch_tweets(self, batch_key: str = "all_accounts") -> Optional[List[Dict[str, Any]]]:
        """Get cached batch of tweets from all accounts"""
        try:
            key = f"{self.BATCH_PREFIX}{batch_key}"
            tweets_json = await self.redis_client.get(key)
            if tweets_json:
                tweets = json.loads(tweets_json)
                logger.info(f"💾 Cache hit for batch: {len(tweets)} tweets")
                return tweets
            return None
        except Exception as e:
            logger.error(f"Error getting batch from cache: {e}")
            return None
    
    async def set_batch_tweets(
        self, 
        tweets: List[Dict[str, Any]], 
        batch_key: str = "all_accounts"
    ):
        """Cache batch of tweets"""
        try:
            key = f"{self.BATCH_PREFIX}{batch_key}"
            tweets_json = json.dumps(tweets)
            await self.redis_client.setex(
                key,
                self.cache_ttl,
                tweets_json
            )
            logger.info(f"✅ Cached batch: {len(tweets)} tweets")
        except Exception as e:
            logger.error(f"Error caching batch: {e}")
    
    async def get_last_fetch_time(self, batch_key: str = "all_accounts") -> Optional[float]:
        """Get timestamp of last fetch"""
        try:
            key = f"{self.LAST_FETCH_PREFIX}{batch_key}"
            timestamp = await self.redis_client.get(key)
            return float(timestamp) if timestamp else None
        except Exception as e:
            logger.error(f"Error getting last fetch time: {e}")
            return None
    
    async def set_last_fetch_time(self, timestamp: float, batch_key: str = "all_accounts"):
        """Set timestamp of last fetch"""
        try:
            key = f"{self.LAST_FETCH_PREFIX}{batch_key}"
            await self.redis_client.setex(
                key,
                self.cache_ttl,
                str(timestamp)
            )
        except Exception as e:
            logger.error(f"Error setting last fetch time: {e}")
    
    async def invalidate_user(self, username: str):
        """Invalidate cache for specific user"""
        try:
            key = f"{self.TWEETS_PREFIX}{username.lower()}"
            await self.redis_client.delete(key)
            logger.info(f"🗑️ Invalidated cache for @{username}")
        except Exception as e:
            logger.error(f"Error invalidating cache: {e}")
    
    async def invalidate_all(self):
        """Invalidate all Twitter caches"""
        try:
            # Delete all keys matching patterns
            patterns = [
                f"{self.TWEETS_PREFIX}*",
                f"{self.BATCH_PREFIX}*",
                f"{self.LAST_FETCH_PREFIX}*"
            ]
            
            deleted = 0
            for pattern in patterns:
                keys = []
                async for key in self.redis_client.scan_iter(match=pattern):
                    keys.append(key)
                
                if keys:
                    deleted += await self.redis_client.delete(*keys)
            
            logger.info(f"🗑️ Invalidated {deleted} Twitter cache entries")
        except Exception as e:
            logger.error(f"Error invalidating all caches: {e}")
    
    async def close(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("✅ Redis cache closed")


# Integration with GameXService
class GameXServiceWithRedis:
    """GameX service with Redis caching"""
    
    def __init__(self):
        self.access_token = settings.GAME_ACCESS_TOKEN
        self.x_accounts = settings.X_ACCOUNTS
        self.client: Optional[Any] = None
        self.agent = None
        
        # Redis cache
        self.cache = TwitterCacheService()
        
        # Rate limiting
        self._min_batch_interval = 60  # seconds
    
    async def initialize(self):
        """Initialize both Twitter client and Redis cache"""
        from virtuals_tweepy import Client
        from app.agents.content_cleaner import get_content_cleaner_agent
        
        # Initialize Twitter client
        self.client = Client(game_twitter_access_token=self.access_token)
        self.agent = get_content_cleaner_agent(create_if_missing=True)
        
        # Initialize Redis
        await self.cache.initialize()
        
        # Pre-cache user IDs
        await self._precache_user_ids()
        
        logger.info("✅ GameX service with Redis initialized")
        return True
    
    async def _precache_user_ids(self):
        """Cache user IDs from Redis or fetch fresh"""
        from virtuals_tweepy.errors import TweepyException
        
        logger.info("🔄 Loading user IDs...")
        cached_count = 0
        
        for username in self.x_accounts:
            clean_username = username.lstrip('@').lower()
            
            # Check Redis first
            user_id = await self.cache.get_user_id(clean_username)
            if user_id:
                cached_count += 1
                continue
            
            # Fetch and cache
            try:
                user_response = self.client.get_user(username=clean_username)
                if user_response.data:
                    await self.cache.set_user_id(clean_username, user_response.data.id)
            except TweepyException as e:
                logger.warning(f"⚠️ Error fetching user @{clean_username}: {e}")
                continue
        
        logger.info(f"✅ User IDs ready ({cached_count} from cache, {len(self.x_accounts) - cached_count} fetched)")
    
    async def fetch_latest_tweets(
        self, 
        max_results: int = 20,
        username: str = None,
        force_refresh: bool = False
    ) -> List[Dict[str, Any]]:
        """Fetch tweets with Redis caching"""
        import time
        
        if username:
            return await self._fetch_user_tweets_cached(username, max_results, force_refresh)
        
        # Check if we should use cache
        if not force_refresh:
            # Check last fetch time
            last_fetch = await self.cache.get_last_fetch_time()
            if last_fetch:
                elapsed = time.time() - last_fetch
                if elapsed < self._min_batch_interval:
                    # Try to get from cache
                    cached_tweets = await self.cache.get_batch_tweets()
                    if cached_tweets:
                        logger.info(f"⚡ Using Redis cache ({int(elapsed)}s old)")
                        return cached_tweets
        
        # Fetch fresh
        logger.info("🔄 Fetching fresh tweets from Twitter API")
        tweets = await self._fetch_all_accounts_fresh(max_results)
        
        # Cache results
        await self.cache.set_batch_tweets(tweets)
        await self.cache.set_last_fetch_time(time.time())
        
        return tweets
    
    async def _fetch_user_tweets_cached(
        self,
        username: str,
        max_results: int,
        force_refresh: bool
    ) -> List[Dict[str, Any]]:
        """Fetch single user with Redis cache"""
        from virtuals_tweepy.errors import TweepyException
        
        clean_username = username.lstrip('@').lower()
        
        # Check cache
        if not force_refresh:
            cached = await self.cache.get_user_tweets(clean_username)
            if cached:
                return cached
        
        # Fetch fresh
        try:
            user_id = await self.cache.get_user_id(clean_username)
            if not user_id:
                user_response = self.client.get_user(username=clean_username)
                if user_response.data:
                    user_id = user_response.data.id
                    await self.cache.set_user_id(clean_username, user_id)
                else:
                    return []
            
            tweets_response = self.client.get_users_tweets(
                id=user_id,
                max_results=min(max_results, 100),
                tweet_fields=['created_at', 'public_metrics'],
                exclude=['retweets', 'replies']
            )
            
            if not tweets_response.data:
                return []
            
            tweets = await self._normalize_tweets(tweets_response.data, clean_username)
            
            # Cache results
            await self.cache.set_user_tweets(clean_username, tweets)
            
            return tweets
            
        except TweepyException as e:
            logger.error(f"Error fetching @{username}: {e}")
            return []
    
    async def _fetch_all_accounts_fresh(self, limit_per_account: int) -> List[Dict[str, Any]]:
        """Fetch from all accounts (implementation from optimized version)"""
        from virtuals_tweepy.errors import TweepyException
        import asyncio
        
        all_tweets = []
        batch_size = 2
        
        for i in range(0, len(self.x_accounts), batch_size):
            batch = self.x_accounts[i:i + batch_size]
            
            tasks = []
            for username in batch:
                clean_username = username.lstrip('@').lower()
                user_id = await self.cache.get_user_id(clean_username)
                if user_id:
                    tasks.append(
                        self._fetch_timeline_safe(user_id, clean_username, limit_per_account)
                    )
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, list):
                    all_tweets.extend(result)
            
            if i + batch_size < len(self.x_accounts):
                await asyncio.sleep(3)
        
        return all_tweets
    
    async def _fetch_timeline_safe(self, user_id: str, username: str, max_results: int):
        """Safe timeline fetch with error handling"""
        from virtuals_tweepy.errors import TweepyException
        
        try:
            response = self.client.get_users_tweets(
                id=user_id,
                max_results=min(max_results, 100),
                tweet_fields=['created_at', 'public_metrics'],
                exclude=['retweets', 'replies']
            )
            
            if response.data:
                return await self._normalize_tweets(response.data, username)
            return []
            
        except TweepyException as e:
            if "429" in str(e):
                logger.warning(f"⏳ Rate limit for @{username}")
            return []
    
    async def _normalize_tweets(self, tweets_data, username: str):
        """Normalize tweet data (same as before)"""
        # Implementation from your original code
        normalized = []
        for tweet in tweets_data:
            # ... normalization logic ...
            pass
        return normalized
    
    async def close(self):
        """Close connections"""
        await self.cache.close()


# Singleton
game_x_service_redis = GameXServiceWithRedis()