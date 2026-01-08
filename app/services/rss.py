"""
RSS News Aggregator
Fetches news from multiple RSS feeds
"""

import httpx
import feedparser
import re
from typing import List, Dict, Any
from loguru import logger
from datetime import datetime


class RSSNewsService:
    """Aggregate news from RSS feeds"""
    
    # Major crypto news RSS feeds
    FEEDS = {
        "cointelegraph": "https://cointelegraph.com/rss",
        "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "decrypt": "https://decrypt.co/feed",
        "theblock": "https://www.theblock.co/rss.xml",
        "bitcoinmagazine": "https://bitcoinmagazine.com/.rss/full/",
        "cryptoslate": "https://cryptoslate.com/feed/",
    }
    
    async def initialize(self):
        """Initialize service"""
        logger.info("✓ RSS News Service initialized")
        return True
    
    async def fetch_news(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Fetch news from RSS feeds
        """
        all_news = []
        
        for source, feed_url in self.FEEDS.items():
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    response = await client.get(feed_url)
                    feed = feedparser.parse(response.text)
                    
                    for entry in feed.entries[:10]:  # 10 per source
                        # Parse published date
                        pub_date = entry.get("published", "")
                        if hasattr(entry, "published_parsed") and entry.published_parsed:
                            try:
                                pub_date = datetime(*entry.published_parsed[:6]).isoformat()
                            except:
                                pass
                        
                        # Get summary/description
                        summary = entry.get("summary", entry.get("description", ""))
                        
                        # Extract tickers
                        tickers = self._extract_tickers(
                            f"{entry.get('title', '')} {summary}"
                        )
                        
                        all_news.append({
                            "news_url": entry.get("link", ""),
                            "url": entry.get("link", ""),
                            "title": entry.get("title", ""),
                            "text": summary,
                            "content": summary,
                            "published_at": pub_date,
                            "date": pub_date,
                            "source_name": source.title(),
                            "author": entry.get("author", ""),
                            "image_url": self._extract_image(entry),
                            "sentiment": "Neutral",
                            "tickers": tickers,
                            "topics": [],
                        })
                    
                    logger.debug(f"✓ Fetched {len(feed.entries[:10])} items from {source}")
                    
            except Exception as e:
                logger.error(f"Error fetching {source} RSS: {e}")
                continue
        
        # Sort by date (newest first)
        all_news.sort(
            key=lambda x: x.get("published_at", ""),
            reverse=True
        )
        
        logger.info(f"✅ Total RSS news fetched: {len(all_news)}")
        return all_news[:limit]
    
    def _extract_image(self, entry) -> str:
        """Extract image from RSS entry"""
        # Check media:thumbnail
        if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
            return entry.media_thumbnail[0].get("url", "")
        
        # Check media:content
        if hasattr(entry, "media_content") and entry.media_content:
            return entry.media_content[0].get("url", "")
        
        # Check enclosures
        if hasattr(entry, "enclosures") and entry.enclosures:
            for enc in entry.enclosures:
                if "image" in enc.get("type", ""):
                    return enc.get("href", "")
        
        return ""
    
    def _extract_tickers(self, text: str) -> List[str]:
        """Extract tickers from text"""
        common_tickers = [
            "BTC", "ETH", "SOL", "USDT", "USDC", "BNB", "XRP", "ADA",
            "DOGE", "MATIC", "DOT", "AVAX", "LINK", "UNI", "ATOM"
        ]
        
        text_upper = text.upper()
        found = []
        
        for ticker in common_tickers:
            if re.search(rf'\b{ticker}\b', text_upper):
                found.append(ticker)
        
        return found
    
    async def close(self):
        """Close service"""
        pass


# Create global instance
rss_news_service = RSSNewsService()