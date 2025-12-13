import httpx
from typing import List, Dict, Any
from app.core.config import settings
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential


class CryptoNewsService:
    def __init__(self):
        self.api_key = settings.CRYPTO_NEWS_API_KEY
        self.base_url = "https://cryptonews-api.com/api/v1"
        self.client = None

        # Lazy validation flags
        self._api_key_validated = False
        self._api_key_invalid = False

    def validate_api_key(self) -> bool:
        """Validate API key before making requests, with lazy evaluation."""
        if self._api_key_validated:
            return True
        
        if self._api_key_invalid:
            return False

        # Missing key
        if not self.api_key:
            logger.error("❌ Missing CRYPTO_NEWS_API_KEY environment variable")
            self._api_key_invalid = True
            return False

        # Obvious invalid key (too short)
        if len(self.api_key) < 10:
            logger.error("❌ CRYPTO_NEWS_API_KEY appears invalid (too short)")
            self._api_key_invalid = True
            return False

        logger.info("✅ CryptoNews API key validated")
        self._api_key_validated = True
        return True

    async def initialize(self):
        """Initialize HTTP client and test connection."""
        try:
            self.client = httpx.AsyncClient(timeout=30.0)

            # Validate key before test request
            if not self.validate_api_key():
                return False

            # Test with a simple request
            response = await self.client.get(
                f"{self.base_url}/category",
                params={
                    "token": self.api_key,
                    "section": "general",
                    "items": 1
                }
            )

            if response.status_code == 200:
                logger.info("✓ CryptoNews API connection verified")
                return True

            if response.status_code == 401:
                logger.error("❌ Invalid API key (401 Unauthorized)")
                self._api_key_invalid = True
                return False

            logger.error(
                f"✗ CryptoNews API verification failed: {response.status_code} {response.text}"
            )
            return False

        except Exception as e:
            logger.error(f"✗ CryptoNews API initialization failed: {str(e)}")
            return False

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def fetch_trending_news(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch trending crypto news via category endpoint."""
        if not self.validate_api_key():
            return []

        try:
            response = await self.client.get(
                f"{self.base_url}/category",
                params={
                    "token": self.api_key,
                    "section": "general",
                    "items": limit
                }
            )

            if response.status_code == 401:
                logger.error("❌ Invalid API key (401 Unauthorized)")
                self._api_key_invalid = True
                return []

            response.raise_for_status()
            data = response.json()

            # Handle API error responses
            if "error" in data:
                logger.error(f"❌ API error: {data['error']}")
                return []

            news_items = self._normalize_news_items(data.get("data", []))
            logger.info(f"✅ Fetched {len(news_items)} trending news items")
            return news_items

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching trending news: {e.response.status_code} - {e.response.text}")
            return []
        except Exception as e:
            logger.error(f"Error fetching trending news: {str(e)}")
            return []

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def fetch_ticker_news(self, tickers: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Fetch news for specific tickers.
        
        Args:
            tickers: Comma-separated tickers (e.g., "BTC,ETH,SOL")
            limit: Number of items to fetch
        """
        if not self.validate_api_key():
            return []

        try:
            logger.info(f"📰 Fetching news for tickers: {tickers}")
            
            response = await self.client.get(
                f"{self.base_url}",
                params={
                    "token": self.api_key,
                    "tickers": tickers,
                    "items": limit
                }
            )

            if response.status_code == 401:
                logger.error("❌ Invalid API key (401 Unauthorized)")
                self._api_key_invalid = True
                return []
            
            if response.status_code == 403:
                error_data = response.json()
                logger.error(f"❌ API forbidden (403): {error_data.get('message', 'Unknown error')}")
                return []

            response.raise_for_status()
            data = response.json()

            # Handle API error responses
            if "error" in data:
                logger.error(f"❌ API error: {data['error']}")
                return []

            news_items = self._normalize_news_items(data.get("data", []))
            logger.info(f"✅ Fetched {len(news_items)} news items for {tickers}")
            return news_items

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching ticker news: {e.response.status_code} - {e.response.text}")
            return []
        except Exception as e:
            logger.error(f"Error fetching ticker news: {str(e)}")
            return []

    def _normalize_news_items(self, items: List[Dict]) -> List[Dict[str, Any]]:
        """Normalize news items to consistent format"""
        news_items = []
        for item in items:
            # ✅ FIX: Keep news_url in the normalized data
            news_items.append({
                "news_url": item.get("news_url", ""),  # ✅ Preserve original field
                "title": item.get("title", ""),
                "text": item.get("text", ""),
                "content": item.get("text", ""),
                "url": item.get("news_url", ""),  # Also keep as 'url' for compatibility
                "published_at": item.get("date", ""),
                "date": item.get("date", ""),
                "source_name": item.get("source_name", ""),
                "image_url": item.get("image_url", ""),
                "sentiment": item.get("sentiment", "Neutral"),
                "tickers": item.get("tickers", []),
                "topics": item.get("topics", [])
            })
        return news_items

    async def close(self):
        """Close the HTTP client."""
        if self.client:
            await self.client.aclose()


# Create global instance
crypto_news_service = CryptoNewsService()