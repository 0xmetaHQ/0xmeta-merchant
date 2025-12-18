"""
Optimized GAME X Service with multi-layer caching and smart rate limiting
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import asyncio
import json
from loguru import logger
from virtuals_tweepy import Client
from virtuals_tweepy.errors import TweepyException

from app.core.config import settings
from app.agents.content_cleaner import get_content_cleaner_agent


class GameXService:
    
    def __init__(self):
        self.access_token = settings.GAME_ACCESS_TOKEN
        self.x_accounts = settings.X_ACCOUNTS
        self.client: Optional[Client] = None
        self.agent = get_content_cleaner_agent(create_if_missing=True)
        
        # Multi-layer caching
        self._user_ids_cache: Dict[str, str] = {}  # username -> user_id
        self._tweets_cache: Dict[str, Dict] = {}  # username -> {tweets, timestamp}
        self._cache_duration = timedelta(minutes=15)  # Cache tweets for 15min
        
        # Rate limiting
        self._last_batch_time = None
        self._min_batch_interval = 60  # seconds between full fetches
        self._fetching_lock = asyncio.Lock()
    
    async def initialize(self):
        """Initialize client and pre-cache user IDs"""
        try:
            self.client = Client(game_twitter_access_token=self.access_token)
            
            try:
                me = self.client.get_me()
                logger.info(f"✓ GAME X authenticated as: @{me.data.username if me.data else 'Unknown'}")
            except Exception as e:
                logger.warning(f"⚠️ Auth verification failed: {e}")
            
            # Pre-cache all user IDs on startup
            await self._precache_user_ids()
            
            logger.info("✓ GAME X SDK initialized with caching")
            return True
            
        except Exception as e:
            logger.error(f"✗ GAME X initialization failed: {e}")
            return False
    
    async def _precache_user_ids(self):
        """Cache all user IDs on startup to avoid repeated lookups"""
        try:
            logger.info("🔄 Pre-caching user IDs for all whitelisted accounts...")
            self._user_ids_cache = await self._batch_fetch_user_ids(self.x_accounts)
            logger.info(f"✅ Cached {len(self._user_ids_cache)} user IDs")
        except Exception as e:
            logger.error(f"❌ Failed to pre-cache user IDs: {e}")
    
    async def fetch_latest_tweets(
        self, 
        max_results: int = 20,
        username: str = None,
        force_refresh: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Fetch tweets with intelligent caching
        
        Args:
            max_results: Max tweets per user
            username: Specific user (optional)
            force_refresh: Force cache bypass
        """
        try:
            if username:
                # Single user fetch
                return await self._fetch_user_tweets_cached(username, max_results, force_refresh)
            else:
                # Fetch all accounts with caching
                return await self._fetch_all_accounts_cached(max_results, force_refresh)
            
        except Exception as e:
            logger.error(f"❌ Error fetching tweets: {e}")
            return []
    
    async def _fetch_all_accounts_cached(
        self, 
        max_results: int,
        force_refresh: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Fetch from all accounts using cache-first strategy
        """
        # Check if we need to respect rate limits
        async with self._fetching_lock:
            now = datetime.now()
            
            if not force_refresh and self._last_batch_time:
                elapsed = (now - self._last_batch_time).total_seconds()
                if elapsed < self._min_batch_interval:
                    logger.info(f"⏱️ Using cached data (fetched {int(elapsed)}s ago)")
                    return self._get_all_cached_tweets()
            
            # Check cache validity
            if not force_refresh and self._is_cache_valid():
                logger.info("💾 All tweets are cached and fresh")
                return self._get_all_cached_tweets()
            
            # Need fresh data - fetch from Twitter
            logger.info(f"🔄 Fetching fresh data from {len(self.x_accounts)} accounts")
            self._last_batch_time = now
            
            return await self._fetch_all_accounts_fresh(max_results)
    
    def _is_cache_valid(self) -> bool:
        """Check if cached tweets are still valid"""
        now = datetime.now()
        for username, cache_data in self._tweets_cache.items():
            cached_time = cache_data.get('timestamp')
            if not cached_time or (now - cached_time) > self._cache_duration:
                return False
        return len(self._tweets_cache) > 0
    
    def _get_all_cached_tweets(self) -> List[Dict[str, Any]]:
        """Get all tweets from cache"""
        all_tweets = []
        for cache_data in self._tweets_cache.values():
            all_tweets.extend(cache_data.get('tweets', []))
        return all_tweets
    
    async def _fetch_all_accounts_fresh(self, limit_per_account: int) -> List[Dict[str, Any]]:
        """
        Fresh fetch from all accounts with optimized batching
        """
        try:
            # Ensure we have user IDs cached
            if not self._user_ids_cache:
                await self._precache_user_ids()
            
            all_tweets = []
            batch_size = 2  # Fetch 2 accounts at a time to avoid rate limits
            valid_accounts = list(self._user_ids_cache.keys())
            
            logger.info(f"📥 Fetching {len(valid_accounts)} accounts in batches of {batch_size}")
            
            for i in range(0, len(valid_accounts), batch_size):
                batch = valid_accounts[i:i + batch_size]
                
                # Fetch batch concurrently
                tasks = []
                for username in batch:
                    user_id = self._user_ids_cache[username]
                    tasks.append(
                        self._fetch_timeline_by_id_with_cache(
                            user_id, username, limit_per_account
                        )
                    )
                
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Collect and cache results
                for username, result in zip(batch, batch_results):
                    if isinstance(result, list) and result:
                        all_tweets.extend(result)
                        # Update cache
                        self._tweets_cache[username] = {
                            'tweets': result,
                            'timestamp': datetime.now()
                        }
                    elif isinstance(result, Exception):
                        logger.debug(f"Fetch error for @{username}: {result}")
                
                # Rate limit protection between batches
                if i + batch_size < len(valid_accounts):
                    await asyncio.sleep(3)  # 3 second delay between batches
            
            logger.info(f"✅ Fetched {len(all_tweets)} fresh tweets, cached for reuse")
            return all_tweets
            
        except Exception as e:
            logger.error(f"💥 Error in fresh fetch: {e}")
            # Return cached data as fallback
            return self._get_all_cached_tweets()
    
    async def _fetch_user_tweets_cached(
        self,
        username: str,
        max_results: int,
        force_refresh: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Fetch tweets for single user with caching
        """
        clean_username = username.lstrip('@').lower()
        
        # Check cache first
        if not force_refresh and clean_username in self._tweets_cache:
            cache_data = self._tweets_cache[clean_username]
            cached_time = cache_data.get('timestamp')
            
            if cached_time and (datetime.now() - cached_time) < self._cache_duration:
                logger.info(f"💾 Using cached tweets for @{clean_username}")
                return cache_data['tweets']
        
        # Fetch fresh
        try:
            # Get user ID from cache or fetch
            if clean_username not in self._user_ids_cache:
                user_response = self.client.get_user(username=clean_username)
                if user_response.data:
                    self._user_ids_cache[clean_username] = user_response.data.id
                else:
                    logger.warning(f"⚠️ User @{clean_username} not found")
                    return []
            
            user_id = self._user_ids_cache[clean_username]
            tweets = await self._fetch_timeline_by_id_with_cache(
                user_id, clean_username, max_results
            )
            
            # Update cache
            self._tweets_cache[clean_username] = {
                'tweets': tweets,
                'timestamp': datetime.now()
            }
            
            return tweets
            
        except Exception as e:
            logger.error(f"Error fetching @{username}: {e}")
            return []
    
    async def _fetch_timeline_by_id_with_cache(
        self,
        user_id: str,
        username: str,
        max_results: int
    ) -> List[Dict[str, Any]]:
        """
        Fetch timeline with built-in retry logic
        """
        try:
            tweets_response = self.client.get_users_tweets(
                id=user_id,
                max_results=min(max_results, 100),
                tweet_fields=['created_at', 'public_metrics'],
                exclude=['retweets', 'replies']
            )
            
            if not tweets_response.data:
                return []
            
            normalized_tweets = await self._normalize_tweets(tweets_response.data, username)
            logger.info(f"✅ Fetched {len(normalized_tweets)} tweets for @{username}")
            return normalized_tweets
            
        except TweepyException as e:
            if "429" in str(e):
                logger.warning(f"⏳ Rate limit for @{username}, using cache if available")
                # Return cached data if available
                if username in self._tweets_cache:
                    return self._tweets_cache[username].get('tweets', [])
            else:
                logger.warning(f"⚠️ Tweepy error for @{username}: {e}")
            return []
        except Exception as e:
            logger.error(f"💥 Error for @{username}: {e}")
            return []
    
    async def search_tweets_by_keywords(
        self, 
        keywords: List[str], 
        max_results: int = 20,
        force_refresh: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Search tweets by keywords from cached/fresh data
        """
        logger.info(f"🔍 Searching for keywords: {', '.join(keywords)}")
        
        # Get all tweets (from cache or fresh fetch)
        all_tweets = await self._fetch_all_accounts_cached(
            max_results=20, 
            force_refresh=force_refresh
        )
        
        # Filter by keywords
        matching_tweets = []
        for tweet in all_tweets:
            text = tweet.get("text", "").lower()
            if any(keyword.lower() in text for keyword in keywords):
                matching_tweets.append(tweet)
                if len(matching_tweets) >= max_results:
                    break
        
        logger.info(f"✅ Found {len(matching_tweets)} matching tweets")
        return matching_tweets
    
    async def _batch_fetch_user_ids(self, usernames: List[str]) -> Dict[str, str]:
        """
        Batch fetch user IDs (cached after first call)
        """
        user_ids_map = {}
        batch_size = 100
        
        try:
            for i in range(0, len(usernames), batch_size):
                batch = usernames[i:i + batch_size]
                clean_batch = [u.lstrip('@').lower() for u in batch]
                
                try:
                    users_response = self.client.get_users(usernames=clean_batch)
                    
                    if users_response.data:
                        for user in users_response.data:
                            user_ids_map[user.username.lower()] = user.id
                        logger.info(f"✓ Fetched {len(users_response.data)} user IDs")
                    
                except TweepyException as e:
                    logger.warning(f"⚠️ Batch lookup failed: {e}")
                    # Fallback to individual lookups
                    for username in clean_batch:
                        try:
                            user_response = self.client.get_user(username=username)
                            if user_response.data:
                                user_ids_map[user_response.data.username.lower()] = user_response.data.id
                        except:
                            continue
                
                if i + batch_size < len(usernames):
                    await asyncio.sleep(1)
        
        except Exception as e:
            logger.error(f"💥 Error in batch ID fetch: {e}")
        
        return user_ids_map
    
    async def _normalize_tweets(
        self, 
        tweets_data: List[Any], 
        default_username: str = ""
    ) -> List[Dict[str, Any]]:
        """Normalize tweet data with AI titles"""
        normalized = []
        
        for tweet in tweets_data:
            try:
                tweet_id = str(tweet.id)
                text = tweet.text if hasattr(tweet, 'text') else ""
                created_at = str(tweet.created_at) if hasattr(tweet, 'created_at') else ""
                username = default_username
                
                # Generate AI title
                if self.agent and text:
                    try:
                        title = await self.agent.generate_title_with_ai(
                            text=text,
                            source="twitter",
                            category="crypto"
                        )
                    except Exception as e:
                        logger.debug(f"AI title failed: {e}")
                        title = f"Tweet by @{username}" if username else "Crypto Tweet"
                else:
                    title = f"Tweet by @{username}" if username else "Crypto Tweet"
                
                metrics = {}
                if hasattr(tweet, 'public_metrics'):
                    metrics = tweet.public_metrics
                
                normalized.append({
                    "source": "twitter",
                    "id": tweet_id,
                    "title": title,
                    "text": text,
                    "username": username,
                    "created_at": created_at,
                    "date": created_at,
                    "url": f"https://twitter.com/{username}/status/{tweet_id}" if username else f"https://twitter.com/i/status/{tweet_id}",
                    "retweet_count": metrics.get('retweet_count', 0),
                    "like_count": metrics.get('like_count', 0),
                    "reply_count": metrics.get('reply_count', 0),
                })
                
            except Exception as e:
                logger.warning(f"⚠️ Error normalizing tweet: {e}")
                continue
        
        return normalized
    
    def clear_cache(self):
        """Clear all caches (useful for testing)"""
        self._tweets_cache.clear()
        self._last_batch_time = None
        logger.info("🗑️ Cache cleared")
    
    async def close(self):
        """Close service"""
        logger.info("✅ GAME X service closed")


# Singleton instance
game_x_service = GameXService()