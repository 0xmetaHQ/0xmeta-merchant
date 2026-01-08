"""
Signal Transformer Agent
Transforms raw CryptoNews and Twitter data into standardized signal format
Now with Content Cleaner integration using GAME X SDK (no Claude API required)
"""

from typing import Dict, Any, List, Optional
import uuid
from datetime import datetime
from app.agents.categorizer import CategorizerAgent
from app.agents.date_normalizer import DateNormalizerAgent
from app.agents.content_cleaner import get_content_cleaner_agent
from loguru import logger


class SignalTransformerAgent:
    """Transforms raw data into signal format with cleaned content"""
    
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
        
        # Try to get content cleaner agent
        try:
            agent = get_content_cleaner_agent(create_if_missing=False)
            if agent:
                # Clean text first with agent
                text = agent.clean_text(text)
        except Exception as e:
            logger.debug(f"Could not use content cleaner for text cleaning: {e}")
        
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
    async def transform_cryptonews_item(
        cls,
        item: Dict[str, Any],
        category: str, 
        index: int,
        clean_content: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Transform CryptoNews item to signal format
        
        Args:
            item: Raw CryptoNews item
            category: Target category
            index: Item index for ID generation
            clean_content: Whether to clean content with GAME X SDK (default: True)
            
        Returns:
            Transformed signal item or None if filtered
        """
        # Generate ID
        oxmeta_id = cls.generate_id("cryptonews", index)
        
        # Normalize date
        normalized_date = DateNormalizerAgent.normalize_date(
            item.get("date") or item.get("published_at")
        )
        
        # Get original title and text
        original_title = item.get("title", "Crypto News Update")
        original_text = item.get("text", "")
        
        # CHANGE: Handle empty text (common with RSS)
        if not original_text or len(original_text) < 20:
            # Use title as text if no description available
            original_text = f"{original_title}. Read full article at source."
        
        # Clean content if enabled
        if clean_content:
            try:
                # Get content cleaner agent (GAME X SDK powered)
                agent = get_content_cleaner_agent(create_if_missing=True)
                
                if agent:
                    # Clean the text
                    cleaned_text = agent.clean_text(original_text)
                    
                    # Check if title needs improvement
                    needs_new_title = (
                        not original_title or
                        len(original_title) < 10 or
                        original_title == "Crypto News Update"
                    )
                    
                    if needs_new_title and cleaned_text:
                        # Generate better title with GAME X SDK AI
                        try:
                            title = await agent.generate_title_with_ai(
                                cleaned_text,
                                "cryptonews",
                                category
                            )
                        except Exception as e:
                            logger.debug(f"AI title generation failed, using fallback: {e}")
                            title = cls.generate_title_from_text(cleaned_text, max_length=80)
                    else:
                        # Clean existing title
                        title = agent.clean_text(original_title)
                    
                    text = cleaned_text
                else:
                    # Agent not available, use originals with basic cleaning
                    logger.debug("Content cleaner agent not available, using basic cleaning")
                    title = original_title
                    text = original_text
            except Exception as e:
                logger.warning(f"Content cleaning failed for news item: {e}")
                title = original_title
                text = original_text
        else:
            # Use original without cleaning
            title = original_title
            text = original_text
        
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
        
        # CHANGE: Use news_url field correctly
        news_url = item.get("news_url") or item.get("url", "")
        
        # CHANGE: Get author/source
        author = item.get("source_name") or item.get("domain", "Unknown")
        
        # Build signal
        return {
            "oxmeta_id": oxmeta_id,
            "category": category,
            "source": "cryptonews",
            "sources": [news_url] if news_url else [],
            "url": news_url,  # ADD: Direct URL field
            "title": title,
            "text": text,
            "sentiment": sentiment,
            "sentiment_value": sentiment_value,
            "feed_categories": feed_categories,
            "timestamp": normalized_date.timestamp(),
            "normalized_date": normalized_date.isoformat(),
            "tokens": tokens,
            "author": author,
            "image_url": item.get("image_url", ""),
            "type": item.get("type", "Article"),
            "original_sentiment": item.get("sentiment"),
            "tickers": item.get("tickers", [])
        }
    
    @classmethod
    async def transform_twitter_item(
        cls,
        item: Dict[str, Any],
        category: str,
        index: int,
        clean_content: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Transform Twitter item to signal format
        
        Args:
            item: Raw Twitter item
            category: Target category
            index: Item index for ID generation
            clean_content: Whether to clean content with GAME X SDK (default: True)
            
        Returns:
            Transformed signal item or None if filtered (spam)
        """
        # Generate ID
        oxmeta_id = cls.generate_id("twitter", index)
        
        # Get tweet identifiers for logging
        username = item.get("username", "")
        tweet_id = item.get("id", "")
        
        # Normalize date
        normalized_date = DateNormalizerAgent.normalize_date(
            item.get("created_at") or item.get("date")
        )
        
        # Get original tweet text
        original_text = item.get("text", "")
        original_title = item.get("title", "")
        
        # Clean content if enabled
        if clean_content:
            try:
                # Get content cleaner agent (GAME X SDK powered)
                agent = get_content_cleaner_agent(create_if_missing=True)
                
                if agent:
                    # Clean the text (remove RT @, URLs, etc.)
                    cleaned_text = agent.clean_text(original_text)
                    
                    # Check if content is spam - filter it out
                    if agent.is_spam_content(cleaned_text):
                        logger.debug(f"Filtered spam tweet: {tweet_id} from @{username}")
                        return None  # Skip spam content
                    
                    # Generate or improve title
                    needs_new_title = (
                        not original_title or
                        original_title.startswith("Tweet by @") or
                        original_title.startswith("RT @") or
                        len(original_title) < 10
                    )
                    
                    if needs_new_title and cleaned_text:
                        # Generate better title with GAME X SDK AI
                        try:
                            title = await agent.generate_title_with_ai(
                                cleaned_text,
                                "twitter",
                                category
                            )
                        except Exception as e:
                            logger.debug(f"AI title generation failed, using fallback: {e}")
                            title = cls.generate_title_from_text(cleaned_text, max_length=80)
                    else:
                        # Clean existing title
                        title = agent.clean_text(original_title)
                    
                    text = cleaned_text
                else:
                    # Agent not available, use originals with basic cleaning
                    logger.debug("Content cleaner agent not available, using basic cleaning")
                    title = original_title or cls.generate_title_from_text(original_text, max_length=80)
                    text = original_text
            except Exception as e:
                logger.warning(f"Content cleaning failed for tweet: {e}")
                title = original_title or cls.generate_title_from_text(original_text, max_length=80)
                text = original_text
        else:
            # Use original without cleaning
            title = original_title or cls.generate_title_from_text(original_text, max_length=80)
            text = original_text
        
        # Determine sentiment
        sentiment, sentiment_value = cls.determine_sentiment(text)
        
        # Extract tokens
        tokens = cls.extract_tokens(text)
        
        # Feed categories
        feed_categories = [category, "twitter"]
        
        # Build tweet URL
        tweet_url = item.get("url", "")
        if not tweet_url and username and tweet_id:
            tweet_url = f"https://x.com/{username}/status/{tweet_id}"
        
        # Build signal
        return {
            "oxmeta_id": oxmeta_id,
            "category": category,
            "source": "twitter",
            "sources": [tweet_url] if tweet_url else [],
            "tweet_url": tweet_url,
            "title": title,
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
    async def transform_items(
        cls,
        news_items: List[Dict[str, Any]],
        tweet_items: List[Dict[str, Any]],
        category: str,
        clean_content: bool = True
    ) -> Dict[str, Any]:
        """
        Transform all items for a category
        
        Args:
            news_items: Raw CryptoNews items
            tweet_items: Raw Twitter items
            category: Target category
            clean_content: Whether to clean content with GAME X SDK (default: True)
            
        Returns:
            {
                "cryptonews": [...],
                "twitter": [...],
                "metadata": {...}
            }
        """
        logger.info(
            f"🔄 Transforming {len(news_items)} news + {len(tweet_items)} tweets "
            f"for category: {category} (clean_content={clean_content}, using GAME X SDK)"
        )
        
        # Transform news items
        transformed_news = []
        for idx, item in enumerate(news_items, start=1):
            try:
                signal = await cls.transform_cryptonews_item(
                    item, 
                    category, 
                    idx,
                    clean_content=clean_content
                )
                if signal:  # Only add if not filtered
                    transformed_news.append(signal)
            except Exception as e:
                logger.error(f"Error transforming news item {idx}: {e}")
                continue
        
        # Transform tweets
        transformed_tweets = []
        for idx, item in enumerate(tweet_items, start=1):
            try:
                signal = await cls.transform_twitter_item(
                    item, 
                    category, 
                    idx,
                    clean_content=clean_content
                )
                if signal:  # Only add if not filtered (spam)
                    transformed_tweets.append(signal)
            except Exception as e:
                logger.error(f"Error transforming tweet {idx}: {e}")
                continue
        
        # Sort by timestamp (newest first)
        transformed_news.sort(key=lambda x: x["timestamp"], reverse=True)
        transformed_tweets.sort(key=lambda x: x["timestamp"], reverse=True)
        
        # Calculate filtering stats
        filtered_news = len(news_items) - len(transformed_news)
        filtered_tweets = len(tweet_items) - len(transformed_tweets)
        
        logger.info(
            f"✅ Transformation complete: "
            f"{len(transformed_news)} news (filtered {filtered_news}), "
            f"{len(transformed_tweets)} tweets (filtered {filtered_tweets})"
        )
        
        return {
            "cryptonews": transformed_news,
            "twitter": transformed_tweets,
            "metadata": {
                "category": category,
                "total_news": len(transformed_news),
                "total_tweets": len(transformed_tweets),
                "total_items": len(transformed_news) + len(transformed_tweets),
                "filtered_news": filtered_news,
                "filtered_tweets": filtered_tweets,
                "content_cleaned": clean_content,
                "processing_method": "GAME X SDK" if clean_content else "None",
                "processed_at": datetime.utcnow().isoformat() + "Z",
                "timestamp": datetime.utcnow().timestamp()
            }
        }