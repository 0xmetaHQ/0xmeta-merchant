"""
CryptoPanic News API Service
Fetches crypto news from CryptoPanic API with proper normalization
"""

import httpx
from typing import List, Dict, Any, Optional
from app.core.config import settings
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential


class CryptoPanicService:
    """CryptoPanic News API Service"""
    
    def __init__(self):
        self.auth_token = settings.CRYPTOPANIC_AUTH_TOKEN
        self.base_url = settings.CRYPTOPANIC_URL 
        self.client = None 

        # Lazy validation flags
        self._auth_token_validated = False
        self._auth_token_invalid = False

    def validate_auth_token(self) -> bool:
        """Validate auth token before making requests, with lazy evaluation."""
        if self._auth_token_validated:
            return True
        
        if self._auth_token_invalid:
            return False

        if not self.auth_token:
            logger.error("❌ Missing CRYPTOPANIC_AUTH_TOKEN environment variable")
            self._auth_token_invalid = True
            return False

        if len(self.auth_token) < 10:
            logger.error("❌ CRYPTOPANIC_AUTH_TOKEN appears invalid (too short)")
            self._auth_token_invalid = True
            return False

        logger.info("✅ CryptoPanic auth token validated")
        self._auth_token_validated = True
        return True

    async def initialize(self):
        """Initialize HTTP client and test connection."""
        try:
            self.client = httpx.AsyncClient(timeout=30.0)

            if not self.validate_auth_token():
                return False

            response = await self.client.get(
                f"{self.base_url}/posts/",
                params={
                    "auth_token": self.auth_token,
                    "public": "true",
                    "kind": "news"
                }
            )

            if response.status_code == 200:
                logger.info("✓ CryptoPanic API connection verified")
                return True

            if response.status_code in [401, 403]:
                logger.error(f"❌ Invalid auth token ({response.status_code})")
                self._auth_token_invalid = True
                return False

            logger.error(f"✗ CryptoPanic API verification failed: {response.status_code}")
            return False

        except Exception as e:
            logger.error(f"✗ CryptoPanic API initialization failed: {str(e)}")
            return False

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def fetch_news(
        self,
        currencies: Optional[str] = None,
        kind: str = "news",
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Fetch news from CryptoPanic."""
        if not self.validate_auth_token():
            return []

        try:
            params = {
                "auth_token": self.auth_token,
                "public": "true",
                "kind": kind
            }
            
            if currencies:
                params["currencies"] = currencies
            
            logger.info(f"📰 Fetching CryptoPanic news (currencies: {currencies or 'all'})")
            
            response = await self.client.get(
                f"{self.base_url}/posts/",
                params=params
            )

            if response.status_code in [401, 403]:
                logger.error(f"❌ Invalid auth token ({response.status_code})")
                self._auth_token_invalid = True
                return []

            response.raise_for_status()
            data = response.json()

            if isinstance(data, dict) and "results" in data:
                results = data["results"]
                limited_results = results[:limit] if limit else results
                news_items = self._normalize_news_items(limited_results)
                logger.info(f"✅ Fetched {len(news_items)} news items from CryptoPanic")
                return news_items
            
            logger.warning(f"⚠️ Unexpected CryptoPanic response format: {type(data)}")
            return []

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching news: {e.response.status_code}")
            return []
        except Exception as e:
            logger.error(f"Error fetching news: {str(e)}")
            return []

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def fetch_ticker_news(self, tickers: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch news for specific tickers."""
        return await self.fetch_news(currencies=tickers, kind="news", limit=limit)

    def _normalize_news_items(self, items: List[Dict]) -> List[Dict[str, Any]]:
        """
        Normalize CryptoPanic news items to internal format.
        """
        if items:
            first = items[0]
            logger.info(f"🔍 DEBUG - CryptoPanic item sample:")
            logger.info(f"  original_url: {first.get('original_url', 'MISSING')}")
            logger.info(f"  image: {first.get('image', 'MISSING')}")
            logger.info(f"  author: {first.get('author', 'MISSING')}")
            logger.info(f"  instruments: {first.get('instruments', 'MISSING')}")
            logger.info(f"  description: {first.get('description', 'MISSING')[:100]}")
    
        news_items = []
        
        for item in items:
            instruments = item.get("instruments", [])
            tickers = [inst.get("code", "") for inst in instruments if inst.get("code")]
            source = item.get("source", {})
            source_name = source.get("title", source.get("domain", "Unknown"))
            source_domain = source.get("domain", "")
            description = item.get("description", "")
            original_url = item.get("original_url", "")  
            cryptopanic_url = item.get("url", "") 
            image = item.get("image", "")
            author = item.get("author", source_name)
            
            if description and len(description) > 20:
                text_content = description
            else:
                text_content = item.get("title", "Crypto news update")
            
            # Get published date
            published_at = item.get("published_at", item.get("created_at", ""))
            
            # Build normalized item
            news_items.append({
                "news_url": original_url,
                "url": original_url,
                "title": item.get("title", "Crypto News Update"),
                "text": text_content,
                "content": text_content,
                "published_at": published_at,
                "date": published_at,
                "source_name": source_name,
                "author": author,
                "image_url": image,
                "sentiment": "Neutral",  # Simplified
                "tickers": tickers,
                "topics": [],
                "votes": item.get("votes", {}),
                "kind": item.get("kind", "news"),
                "domain": source_domain,
                "slug": item.get("slug", ""),
                "panic_score": item.get("panic_score", 0),
                "cryptopanic_url": cryptopanic_url,
            })
        
        return news_items

    async def close(self):
        """Close the HTTP client."""
        if self.client:
            await self.client.aclose()


cryptopanic_service = CryptoPanicService()