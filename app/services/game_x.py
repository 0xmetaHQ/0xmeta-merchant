"""
GAME X Service using official GAME SDK
Integrates with Twitter/X data through GAME X API
"""

from typing import List, Dict, Any
from app.core.config import settings
from loguru import logger
from game_sdk.game.worker import Worker
from game_sdk.game.custom_types import Function, Argument, FunctionResultStatus
import httpx


class GameXService:
    """Service for interacting with GAME X API using official SDK"""
    
    def __init__(self):
        self.api_key = settings.GAME_API_KEY
        self.access_token = settings.GAME_ACCESS_TOKEN
        self.x_accounts = settings.X_ACCOUNTS
        self.worker = None
        self.client = None
    
    async def initialize(self):
        """Initialize GAME X SDK worker and verify connection"""
        try:
            # Initialize HTTP client for direct API calls
            self.client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "X-API-Key": self.api_key
                }
            )
            
            # Initialize GAME SDK Worker
            self.worker = Worker(
                api_key=self.api_key,
                description="Crypto news aggregation agent for Twitter/X data",
                instruction=(
                    "You are a crypto news aggregation agent that fetches and processes "
                    "Twitter/X posts from monitored crypto accounts."
                ),
                get_state_fn=lambda result, state: state or {},
                action_space=[]  # We'll define actions as needed
            )
            
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
            max_results: Maximum number of tweets to fetch
            username: Optional specific username to fetch from
            
        Returns:
            List of tweet dictionaries
        """
        try:
            if username:
                # Fetch from specific user
                tweets = await self._fetch_user_tweets(username, max_results)
            else:
                # Fetch from all monitored accounts
                tweets = await self._fetch_all_accounts(max_results // len(self.x_accounts))
            
            logger.info(f"Fetched {len(tweets)} tweets from GAME X API")
            return tweets
            
        except Exception as e:
            logger.error(f"Error fetching tweets: {str(e)}")
            return []
    
    async def _fetch_user_tweets(
        self, 
        username: str, 
        max_results: int
    ) -> List[Dict[str, Any]]:
        """Fetch tweets from a specific user using GAME X API"""
        try:
            # Using GAME X API endpoint for user tweets
            response = await self.client.get(
                f"https://api.game.virtuals.io/api/twitter/user/{username}/tweets",
                params={"max_results": max_results}
            )
            
            if response.status_code == 200:
                data = response.json()
                return self._normalize_tweets(data.get("data", []))
            else:
                logger.warning(f"Failed to fetch tweets for @{username}: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching tweets for @{username}: {str(e)}")
            return []
    
    async def _fetch_all_accounts(self, limit_per_account: int) -> List[Dict[str, Any]]:
        """Fetch tweets from all monitored accounts"""
        all_tweets = []
        
        for account in self.x_accounts:
            tweets = await self._fetch_user_tweets(account, limit_per_account)
            all_tweets.extend(tweets)
        
        return all_tweets
    
    async def search_tweets_by_keywords(
    self, 
    keywords: List[str], 
    max_results: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search tweets by keywords across monitored accounts.
        Falls back to fetching recent tweets and filtering locally if API search unavailable.
        
        Args:
            keywords: List of keywords to search for
            max_results: Maximum results to return
            
        Returns:
            List of matching tweets
        """
        try:
            # Build search query
            query = " OR ".join(keywords)
            
            # Try searching using GAME X API
            response = await self.client.get(
                "https://api.game.virtuals.io/api/twitter/search",
                params={
                    "query": query,
                    "max_results": max_results
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                tweets = self._normalize_tweets(data.get("data", []))
                logger.info(f"Found {len(tweets)} tweets for keywords: {', '.join(keywords)}")
                return tweets
            elif response.status_code == 404:
                # Search endpoint not available, fallback to fetching and filtering
                logger.info("Search endpoint unavailable, using fallback method")
                return await self._search_tweets_fallback(keywords, max_results)
            else:
                logger.warning(f"Tweet search failed: {response.status_code}, using fallback")
                return await self._search_tweets_fallback(keywords, max_results)
                
        except Exception as e:
            logger.error(f"Error searching tweets: {str(e)}, using fallback")
            return await self._search_tweets_fallback(keywords, max_results)


    async def _search_tweets_fallback(
        self, 
        keywords: List[str], 
        max_results: int
    ) -> List[Dict[str, Any]]:
        """
        Fallback method: Fetch recent tweets and filter by keywords locally
        
        Args:
            keywords: Keywords to search for
            max_results: Maximum results to return
            
        Returns:
            Filtered tweets matching keywords
        """
        try:
            # Fetch more tweets than needed since we'll be filtering
            all_tweets = await self._fetch_all_accounts(limit_per_account=20)
            
            # Filter tweets by keywords
            matching_tweets = []
            for tweet in all_tweets:
                text = tweet.get("text", "").lower()
                if any(keyword.lower() in text for keyword in keywords):
                    matching_tweets.append(tweet)
                    if len(matching_tweets) >= max_results:
                        break
            
            logger.info(
                f"Fallback search found {len(matching_tweets)} tweets matching keywords: "
                f"{', '.join(keywords)}"
            )
            return matching_tweets
            
        except Exception as e:
            logger.error(f"Fallback search failed: {str(e)}")
            return []

    async def search_related_posts(self, keywords: List[str]) -> List[Dict[str, Any]]:
        """
        Search for posts related to news keywords across all monitored accounts
        
        Args:
            keywords: Keywords from news articles
            
        Returns:
            Related tweets
        """
        all_tweets = []
        
        # Search by keywords
        keyword_tweets = await self.search_tweets_by_keywords(keywords, max_results=30)
        all_tweets.extend(keyword_tweets)
        
        # Also get recent tweets from all accounts
        recent_tweets = await self._fetch_all_accounts(limit_per_account=5)
        
        # Filter recent tweets by keywords
        for tweet in recent_tweets:
            text = tweet.get("text", "").lower()
            if any(keyword.lower() in text for keyword in keywords):
                if tweet not in all_tweets:  # Avoid duplicates
                    all_tweets.append(tweet)
        
        logger.info(f"Found {len(all_tweets)} related tweets for keywords")
        return all_tweets
    
    def _normalize_tweets(self, tweets_data: List[Dict]) -> List[Dict[str, Any]]:
        """
        Normalize tweet data to consistent format
        
        Args:
            tweets_data: Raw tweet data from API
            
        Returns:
            Normalized tweet dictionaries
        """
        normalized = []
        
        for tweet in tweets_data:
            try:
                # Extract tweet data
                tweet_id = tweet.get("id", "")
                text = tweet.get("text", "")
                author_id = tweet.get("author_id", "")
                username = tweet.get("username", "") or self._extract_username(tweet)
                created_at = tweet.get("created_at", "")
                
                # Get engagement metrics
                metrics = tweet.get("public_metrics", {})
                retweet_count = metrics.get("retweet_count", 0)
                like_count = metrics.get("like_count", 0)
                reply_count = metrics.get("reply_count", 0)
                quote_count = metrics.get("quote_count", 0)
                
                # Build normalized tweet
                normalized_tweet = {
                    "source": "twitter",
                    "id": tweet_id,
                    "text": text,
                    "author_id": author_id,
                    "username": username,
                    "created_at": created_at,
                    "date": created_at,  # For date normalization
                    "url": f"https://twitter.com/{username}/status/{tweet_id}" if username else "",
                    "retweet_count": retweet_count,
                    "like_count": like_count,
                    "reply_count": reply_count,
                    "quote_count": quote_count,
                    "entities": tweet.get("entities", {}),
                    "referenced_tweets": tweet.get("referenced_tweets", []),
                }
                
                normalized.append(normalized_tweet)
                
            except Exception as e:
                logger.warning(f"Error normalizing tweet: {str(e)}")
                continue
        
        return normalized
    
    def _extract_username(self, tweet: Dict) -> str:
        """Extract username from tweet data"""
        # Try different fields where username might be
        if "user" in tweet:
            return tweet["user"].get("username", "")
        if "includes" in tweet and "users" in tweet["includes"]:
            users = tweet["includes"]["users"]
            if users:
                return users[0].get("username", "")
        return ""
    
    async def close(self):
        """Close HTTP client"""
        if self.client:
            await self.client.aclose()
            logger.info("GAME X service closed")


# Singleton instance
game_x_service = GameXService()