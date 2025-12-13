"""
Signal Transformer Agent
Transforms raw CryptoNews and Twitter data into standardized signal format
"""

from typing import Dict, Any, List
import uuid
from datetime import datetime
from app.agents.categorizer import CategorizerAgent
from app.agents.date_normalizer import DateNormalizerAgent
from loguru import logger


class SignalTransformerAgent:
    """Transforms raw data into signal format with original titles"""
    
    MERCHANT_ID = "0xmeta_merchant"
    
    @classmethod
    def generate_id(cls, source: str, index: int) -> str:
        """
        Generate unique ID for each item
        
        Args:
            source: 'cryptonews' or 'twitter'
            index: Item index
            
        Returns:
            ID like '0xmeta_1_merchant'
        """
        return f"0xmeta_{index}_{cls.MERCHANT_ID}"
    
    @classmethod
    def generate_title_from_text(cls, text: str, max_length: int = 100) -> str:
        """
        Generate a short title from long text (fallback only)
        Simple extraction of first sentence or key phrase
        
        Args:
            text: Full text content
            max_length: Maximum title length
            
        Returns:
            Generated title
        """
        if not text:
            return "Crypto Update"
        
        # Clean text
        text = text.strip()
        
        # Try to get first sentence
        sentences = text.split('.')
        if sentences and len(sentences[0]) > 10:
            title = sentences[0].strip()
        else:
            # Take first max_length characters
            title = text[:max_length]
        
        # Remove emojis at start for cleaner title
        title = title.lstrip('🚨🔥⚡💰📈📉🎯')
        
        # Add ellipsis if truncated
        if len(title) >= max_length - 3:
            title = title[:max_length - 3] + "..."
        
        return title.strip()
    
    @classmethod
    def determine_sentiment(cls, text: str, existing_sentiment: str = None) -> tuple:
        """
        Determine sentiment from text or use existing
        
        Returns:
            (sentiment, sentiment_value)
        """
        if existing_sentiment:
            sentiment_map = {
                "Positive": ("bullish", 0.7),
                "Negative": ("bearish", 0.3),
                "Neutral": ("neutral", 0.5)
            }
            return sentiment_map.get(existing_sentiment, ("neutral", 0.5))
        
        # Simple keyword-based sentiment
        text_lower = text.lower()
        
        bullish_keywords = [
            "surge", "rally", "gain", "up", "rise", "bull", "pump",
            "ath", "high", "bullish", "moon", "breakout"
        ]
        bearish_keywords = [
            "drop", "fall", "down", "bear", "crash", "dump",
            "low", "bearish", "decline", "sell", "liquidation"
        ]
        
        bullish_count = sum(1 for kw in bullish_keywords if kw in text_lower)
        bearish_count = sum(1 for kw in bearish_keywords if kw in text_lower)
        
        if bullish_count > bearish_count:
            return ("bullish", min(0.6 + (bullish_count * 0.1), 0.95))
        elif bearish_count > bullish_count:
            return ("bearish", max(0.4 - (bearish_count * 0.1), 0.05))
        else:
            return ("neutral", 0.5)
    
    @classmethod
    def extract_tokens(cls, text: str, tickers: List[str] = None) -> List[str]:
        """
        Extract token symbols from text
        
        Args:
            text: Text content
            tickers: Existing tickers list
            
        Returns:
            List of token symbols like ["$BTC", "$ETH"]
        """
        tokens = set()
        
        # Add existing tickers
        if tickers:
            tokens.update([f"${t.upper()}" for t in tickers])
        
        # Common crypto symbols
        common_tokens = [
            "BTC", "ETH", "SOL", "USDT", "USDC", "BNB", "XRP", "ADA",
            "DOGE", "MATIC", "DOT", "AVAX", "LINK", "UNI", "ATOM"
        ]
        
        # Check text for mentions
        text_upper = text.upper()
        for token in common_tokens:
            if token in text_upper or f"${token}" in text_upper:
                tokens.add(f"${token}")
        
        return sorted(list(tokens))
    
    @classmethod
    def transform_cryptonews_item(
        cls,
        item: Dict[str, Any],
        category: str,
        index: int
    ) -> Dict[str, Any]:
        """
        Transform CryptoNews item to signal format
        
        Args:
            item: Raw CryptoNews item
            category: Target category
            index: Item index for ID generation
            
        Returns:
            Transformed signal item
        """
        # Generate ID
        oxmeta_id = cls.generate_id("cryptonews", index)
        
        # Normalize date
        normalized_date = DateNormalizerAgent.normalize_date(
            item.get("date") or item.get("published_at")
        )
        
        # ✅ FIX: Use the original title directly from API, no generation
        title = item.get("title", "Crypto News Update")
        
        # Text content
        text = item.get("text", "")
        
        # Determine sentiment
        sentiment, sentiment_value = cls.determine_sentiment(
            text,
            item.get("sentiment")
        )
        
        # Extract tokens
        tokens = cls.extract_tokens(
            f"{title} {text}",
            item.get("tickers", [])
        )
        
        # Categorize into feed categories
        feed_categories = [category]
        if item.get("topics"):
            feed_categories.extend(item.get("topics", []))
        
        # ✅ FIX: Use news_url field correctly
        news_url = item.get("news_url", "")
        
        # Build signal
        return {
            "oxmeta_id": oxmeta_id,
            "category": category,
            "source": "cryptonews",
            "sources": [news_url],  # ✅ Use news_url from normalized data
            "title": title,  # ✅ Original title, not generated
            "text": text,
            "sentiment": sentiment,
            "sentiment_value": sentiment_value,
            "feed_categories": feed_categories,
            "timestamp": normalized_date.timestamp(),
            "normalized_date": normalized_date.isoformat(),
            "tokens": tokens,
            "author": item.get("source_name", "Unknown"),
            "image_url": item.get("image_url"),
            "type": item.get("type", "Article"),
            "original_sentiment": item.get("sentiment"),
            "tickers": item.get("tickers", [])
        }
    
    @classmethod
    def transform_twitter_item(
        cls,
        item: Dict[str, Any],
        category: str,
        index: int
    ) -> Dict[str, Any]:
        """
        Transform Twitter item to signal format
        
        Args:
            item: Raw Twitter item
            category: Target category
            index: Item index for ID generation
            
        Returns:
            Transformed signal item
        """
        # Generate ID
        oxmeta_id = cls.generate_id("twitter", index)
        
        # Normalize date
        normalized_date = DateNormalizerAgent.normalize_date(
            item.get("created_at") or item.get("date")
        )
        
        # Get tweet text
        text = item.get("text", "")
        
        # ✅ FIX: Use original title from API if exists, only generate as fallback
        title = item.get("title", "")
        if not title:
            # Only generate if API didn't provide a title
            title = cls.generate_title_from_text(text, max_length=80)
        
        # Determine sentiment
        sentiment, sentiment_value = cls.determine_sentiment(text)
        
        # Extract tokens
        tokens = cls.extract_tokens(text)
        
        # Feed categories
        feed_categories = [category, "twitter"]
        
        # Build tweet URL
        username = item.get("username", "")
        tweet_id = item.get("id", "")
        tweet_url = item.get("url", "")
        if not tweet_url and username and tweet_id:
            tweet_url = f"https://x.com/{username}/status/{tweet_id}"
        
        # Build signal
        return {
            "oxmeta_id": oxmeta_id,
            "category": category,
            "source": "twitter",
            "sources": [tweet_url] if tweet_url else [],  # Array with tweet URL
            "tweet_url": tweet_url,
            "title": title,  # ✅ Use original API title or fallback to generated
            "text": text,
            "sentiment": sentiment,
            "sentiment_value": sentiment_value,
            "feed_categories": feed_categories,
            "timestamp": normalized_date.timestamp(),
            "normalized_date": normalized_date.isoformat(),
            "tokens": tokens,
            "author": f"@{username}" if username else "Unknown",
            "username": username,
            "tweet_id": tweet_id,
            "engagement": {
                "retweets": item.get("retweet_count", 0),
                "likes": item.get("like_count", 0),
                "replies": item.get("reply_count", 0),
                "quotes": item.get("quote_count", 0)
            },
            "entities": item.get("entities", {})
        }
    
    @classmethod
    def transform_items(
        cls,
        news_items: List[Dict[str, Any]],
        tweet_items: List[Dict[str, Any]],
        category: str
    ) -> Dict[str, Any]:
        """
        Transform all items for a category
        
        Args:
            news_items: Raw CryptoNews items
            tweet_items: Raw Twitter items
            category: Target category
            
        Returns:
            {
                "cryptonews": [...],
                "twitter": [...],
                "metadata": {...}
            }
        """
        # Transform news items
        transformed_news = []
        for idx, item in enumerate(news_items, start=1):
            try:
                signal = cls.transform_cryptonews_item(item, category, idx)
                transformed_news.append(signal)
            except Exception as e:
                logger.error(f"Error transforming news item: {e}")
                continue
        
        # Transform tweets
        transformed_tweets = []
        for idx, item in enumerate(tweet_items, start=1):
            try:
                signal = cls.transform_twitter_item(item, category, idx)
                transformed_tweets.append(signal)
            except Exception as e:
                logger.error(f"Error transforming tweet: {e}")
                continue
        
        # Sort by timestamp (newest first)
        transformed_news.sort(key=lambda x: x["timestamp"], reverse=True)
        transformed_tweets.sort(key=lambda x: x["timestamp"], reverse=True)
        
        return {
            "cryptonews": transformed_news,
            "twitter": transformed_tweets,
            "metadata": {
                "category": category,
                "total_news": len(transformed_news),
                "total_tweets": len(transformed_tweets),
                "total_items": len(transformed_news) + len(transformed_tweets),
                "processed_at": datetime.utcnow().isoformat() + "Z",
                "timestamp": datetime.utcnow().timestamp()
            }
        }