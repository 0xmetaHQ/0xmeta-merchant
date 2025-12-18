"""
GAME X Service using virtuals-tweepy for Twitter/X data fetching
"""

from typing import List, Dict, Any, Optional
from app.core.config import settings
from loguru import logger
from virtuals_tweepy import Client
from virtuals_tweepy.errors import TweepyException
import asyncio

from app.agents.content_cleaner import get_content_cleaner_agent


class GameXService:
    """Service for interacting with Twitter/X API using virtuals-tweepy (GAME X)"""
    
    def __init__(self):
        self.access_token = settings.GAME_ACCESS_TOKEN
        self.x_accounts = settings.X_ACCOUNTS
        self.client: Optional[Client] = None
        # Get content cleaner agent once during init
        self.agent = get_content_cleaner_agent(create_if_missing=True)
    
    async def initialize(self):
        """Initialize GAME X Twitter client and verify connection"""
        try:
            self.client = Client(
                game_twitter_access_token=self.access_token
            )
            
            try:
                me = self.client.get_me()
                logger.info(f"✓ GAME X Twitter API initialized successfully - Authenticated as: @{me.data.username if me.data else 'Unknown'}")
            except Exception as e:
                logger.warning(f"⚠️ Could not verify authentication, but client initialized: {str(e)}")
            
            logger.info("✓ GAME X SDK initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"✗ GAME X SDK initialization failed: {str(e)}")
            return False
    
    async def fetch_latest_tweets(
        self, 
        max_results: int = 20,
        username: str = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch latest tweets from monitored accounts or specific user
        
        Args:
            max_results: Maximum number of tweets to fetch per user
            username: Optional specific username to fetch from
            
        Returns:
            List of tweet dictionaries
        """
        try:
            if username:
                tweets = await self._fetch_user_tweets(username, max_results)
            else:
                tweets = await self._fetch_all_accounts(max_results // len(self.x_accounts)) 
            
            logger.info(f"✅ Fetched {len(tweets)} tweets from GAME X Twitter API")
            return tweets
            
        except Exception as e:
            logger.error(f"❌ Error fetching tweets: {str(e)}")
            return []
    
    async def _fetch_user_tweets(
        self, 
        username: str, 
        max_results: int
    ) -> List[Dict[str, Any]]:
        """
        Fetch tweets from a specific user using virtuals-tweepy
        
        Args:
            username: Twitter username (without @)
            max_results: Maximum number of tweets to fetch
            
        Returns:
            List of normalized tweet dictionaries
        """
        try:
            logger.info(f"🔍 Fetching tweets for @{username} (max: {max_results})")
            
            if not self.client:
                logger.error("❌ Twitter client not initialized")
                return []
            
            clean_username = username.lstrip('@')
            
            user_response = self.client.get_user(username=clean_username)
            
            if not user_response.data:
                logger.warning(f"⚠️ User @{clean_username} not found")
                return []
            
            user_id = user_response.data.id
            
            tweets_response = self.client.get_users_tweets(
                id=user_id,
                max_results=min(max_results, 100),
                tweet_fields=['created_at', 'public_metrics'],
                expansions=['author_id'],
                user_fields=['username']
            )
            
            if not tweets_response.data:
                logger.info(f"ℹ️ No tweets found for @{clean_username}")
                return []
            
            # ✅ FIXED - await the async function
            normalized_tweets = await self._normalize_tweets(tweets_response.data, clean_username)
            
            logger.info(f"✅ Successfully fetched {len(normalized_tweets)} tweets for @{clean_username}")
            return normalized_tweets
                
        except TweepyException as e:
            logger.error(f"💥 Tweepy error fetching tweets for @{username}: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"💥 Error fetching tweets for @{username}: {str(e)}", exc_info=True)
            return []
    
    async def _fetch_all_accounts(self, limit_per_account: int) -> List[Dict[str, Any]]:
        """
        OPTIMIZED: Fetch tweets from all monitored accounts using batch processing
        """
        try:
            logger.info(f"📥 Fetching tweets from {len(self.x_accounts)} whitelisted accounts (optimized)")
            
            # Step 1: Batch fetch user IDs for all accounts at once
            user_ids_map = await self._batch_fetch_user_ids(self.x_accounts)
            
            if not user_ids_map:
                logger.warning("⚠️ No valid user IDs found")
                return []
            
            # Step 2: Fetch timelines in controlled batches
            all_tweets = []
            batch_size = 3  # Fetch 3 accounts concurrently
            valid_accounts = list(user_ids_map.keys())
            
            for i in range(0, len(valid_accounts), batch_size):
                batch = valid_accounts[i:i + batch_size]
                
                # Fetch batch concurrently
                tasks = []
                for username in batch:
                    user_id = user_ids_map[username]
                    tasks.append(self._fetch_timeline_by_id(user_id, username, limit_per_account))
                
                # ✅ FIXED - properly await asyncio.gather
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Collect results
                for result in batch_results:
                    if isinstance(result, list):
                        all_tweets.extend(result)
                    elif isinstance(result, Exception):
                        logger.debug(f"Batch fetch error: {result}")
                
                # Rate limit protection: wait between batches
                if i + batch_size < len(valid_accounts):
                    await asyncio.sleep(2)
            
            logger.info(f"✅ Fetched {len(all_tweets)} tweets from {len(valid_accounts)} accounts")
            return all_tweets
            
        except Exception as e:
            logger.error(f"💥 Error in optimized batch fetch: {e}")
            return []

    async def _batch_fetch_user_ids(self, usernames: List[str]) -> Dict[str, str]:
        """
        Fetch user IDs for multiple usernames in batches
        Twitter API allows up to 100 usernames per request
        
        Returns:
            Dict mapping username -> user_id
        """
        user_ids_map = {}
        batch_size = 100  # Twitter API limit
        
        try:
            for i in range(0, len(usernames), batch_size):
                batch = usernames[i:i + batch_size]
                
                # Clean usernames
                clean_batch = [username.lstrip('@') for username in batch]
                
                # Fetch batch of users
                try:
                    users_response = self.client.get_users(usernames=clean_batch)
                    
                    if users_response.data:
                        for user in users_response.data:
                            user_ids_map[user.username.lower()] = user.id
                        logger.info(f"✓ Fetched {len(users_response.data)} user IDs from batch")
                    else:
                        logger.warning(f"⚠️ No users found in batch: {clean_batch}")
                        
                except TweepyException as e:
                    logger.warning(f"⚠️ Batch user lookup failed: {e}")
                    # Fallback: try individual lookups for this batch
                    for username in clean_batch:
                        try:
                            user_response = self.client.get_user(username=username)
                            if user_response.data:
                                user_ids_map[user_response.data.username.lower()] = user_response.data.id
                        except:
                            continue
                
                # Small delay between batches
                if i + batch_size < len(usernames):
                    await asyncio.sleep(1)
        
        except Exception as e:
            logger.error(f"💥 Error in batch user ID fetch: {e}")
        
        return user_ids_map

    async def _fetch_timeline_by_id(
        self,
        user_id: str,
        username: str,
        max_results: int
    ) -> List[Dict[str, Any]]:
        """
        Fetch timeline for a user by their ID (more efficient than username lookup)
        
        Args:
            user_id: Twitter user ID
            username: Username for normalization
            max_results: Max tweets to fetch
            
        Returns:
            List of normalized tweets
        """
        try:
            tweets_response = self.client.get_users_tweets(
                id=user_id,
                max_results=min(max_results, 100),
                tweet_fields=['created_at', 'public_metrics'],
                exclude=['retweets', 'replies']  # Focus on original tweets only
            )
            
            if not tweets_response.data:
                return []
            
            # ✅ FIXED - await the async function
            normalized_tweets = await self._normalize_tweets(tweets_response.data, username)
            return normalized_tweets
            
        except TweepyException as e:
            if "429" in str(e):
                logger.warning(f"⏳ Rate limit hit for @{username}, skipping")
            else:
                logger.warning(f"⚠️ Error fetching @{username}: {e}")
            return []
        except Exception as e:
            logger.error(f"💥 Unexpected error for @{username}: {e}")
            return []

    async def search_tweets_by_keywords(
        self, 
        keywords: List[str], 
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search tweets by keywords ONLY from whitelisted accounts
        
        Args:
            keywords: List of keywords to search for
            max_results: Maximum results to return
            
        Returns:
            List of matching tweets from whitelisted accounts
        """
        logger.info(f"🔍 Searching whitelisted accounts for keywords: {', '.join(keywords)}")
        
        # Fetch from whitelisted accounts
        all_tweets = await self._fetch_all_accounts(limit_per_account=20)
        
        # Filter by keywords (case-insensitive)
        matching_tweets = []
        for tweet in all_tweets:
            text = tweet.get("text", "").lower()
            if any(keyword.lower() in text for keyword in keywords):
                matching_tweets.append(tweet)
                if len(matching_tweets) >= max_results:
                    break
        
        logger.info(
            f"✅ Found {len(matching_tweets)} tweets from whitelisted accounts matching keywords"
        )
        return matching_tweets

    async def search_related_posts(self, keywords: List[str]) -> List[Dict[str, Any]]:
        """
        Search for posts related to news keywords from whitelisted accounts
        
        Args:
            keywords: Keywords from news articles
            
        Returns:
            Related tweets from whitelisted accounts
        """
        logger.info(f"🔄 Searching whitelisted accounts for related posts: {keywords}")
        
        # Fetch recent tweets from monitored accounts
        recent_tweets = await self._fetch_all_accounts(limit_per_account=10)
        
        # Filter by keywords
        matching_tweets = []
        for tweet in recent_tweets:
            text = tweet.get("text", "").lower()
            if any(keyword.lower() in text for keyword in keywords):
                matching_tweets.append(tweet)
        
        logger.info(f"✅ Found {len(matching_tweets)} related tweets from whitelisted accounts")
        return matching_tweets[:30]
    
    async def _normalize_tweets(
        self, 
        tweets_data: List[Any], 
        default_username: str = ""
    ) -> List[Dict[str, Any]]:
        """
        ✅ PROPERLY ASYNC: Normalize tweet data with AI-generated titles
        
        Args:
            tweets_data: Raw tweet data from Tweepy
            default_username: Default username if not available in tweet
            
        Returns:
            Normalized tweet dictionaries with AI-generated titles
        """
        normalized = []
        
        for tweet in tweets_data:
            try:
                tweet_id = str(tweet.id)
                text = tweet.text if hasattr(tweet, 'text') else ""
                created_at = str(tweet.created_at) if hasattr(tweet, 'created_at') else ""
                
                # Use the username from the account we fetched from
                username = default_username
                
                # ✅ Generate AI title for each tweet
                if self.agent and text:
                    try:
                        # Generate title with AI based on tweet content
                        title = await self.agent.generate_title_with_ai(
                            text=text,
                            source="twitter",
                            category="crypto"  # Default category, will be refined in transformer
                        )
                    except Exception as e:
                        logger.debug(f"AI title generation failed for tweet {tweet_id}: {e}")
                        # Fallback to simple title
                        title = f"Tweet by @{username}" if username else "Crypto Tweet"
                else:
                    # Fallback if agent not available
                    title = f"Tweet by @{username}" if username else "Crypto Tweet"
                
                # Get engagement metrics
                metrics = {}
                if hasattr(tweet, 'public_metrics'):
                    metrics = tweet.public_metrics
                
                retweet_count = metrics.get('retweet_count', 0)
                like_count = metrics.get('like_count', 0)
                reply_count = metrics.get('reply_count', 0)
                
                # Build normalized tweet
                normalized_tweet = {
                    "source": "twitter",
                    "id": tweet_id,
                    "title": title,  # ✅ AI-generated title based on content
                    "text": text,
                    "username": username,
                    "created_at": created_at,
                    "date": created_at,
                    "url": f"https://twitter.com/{username}/status/{tweet_id}" if username else f"https://twitter.com/i/status/{tweet_id}",
                    "retweet_count": retweet_count,
                    "like_count": like_count,
                    "reply_count": reply_count,
                }
                
                normalized.append(normalized_tweet)
                
            except Exception as e:
                logger.warning(f"⚠️ Error normalizing tweet: {str(e)}")
                continue
        
        return normalized
    
    async def close(self):
        """Close Twitter client"""
        logger.info("✅ GAME X service closed")


# Singleton instance
game_x_service = GameXService()