"""
Data Processor Agent - Processes and categorizes data from separate sources
DOES NOT MERGE - Keeps CryptoPanic and X (Twitter) as separate sources
"""

from typing import Dict, Any, List, Tuple
from app.agents.date_normalizer import DateNormalizerAgent
from app.agents.categorizer import CategorizerAgent
from loguru import logger
import uuid
import time


class DataProcessorAgent:
    """Agent for processing and categorizing data from separate sources"""
    
    @classmethod
    def process_by_category(
        cls, 
        category: str, 
        news_items: List[Dict[str, Any]], 
        tweets: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Process news and tweets for a specific category (kept separate)
        
        Args:
            category: Target category name
            news_items: List of news articles from CryptoPanic API
            tweets: List of tweets from GAME X API
            
        Returns:
            {
                "cryptopanic": [...],  # Filtered news items
                "twitter": [...],      # Filtered tweets
                "metadata": {...}
            }
        """
        # Process CryptoPanic items
        processed_news = []
        for item in news_items:
            # Normalize date
            normalized_date = DateNormalizerAgent.normalize_date(
                item.get("date") or item.get("published_at")
            )
            
            # Categorize
            item_category = CategorizerAgent.categorize_item(item)
            
            # Filter by category
            if item_category == category or category == "trends":
                processed_item = {
                    "source": "cryptopanic", 
                    "news_url": item.get("news_url", ""),
                    "image_url": item.get("image_url", ""),
                    "title": item.get("title", ""),
                    "text": item.get("text", ""),
                    "source_name": item.get("source_name", ""),
                    "date": item.get("date", ""),
                    "normalized_date": normalized_date.isoformat(),
                    "timestamp": normalized_date.timestamp(),
                    "topics": item.get("topics", []),
                    "sentiment": item.get("sentiment", "Neutral"),
                    "type": item.get("type", "Article"),
                    "tickers": item.get("tickers", []),
                    "category": item_category
                }
                processed_news.append(processed_item)
        
        # Process Twitter/X items
        processed_tweets = []
        for item in tweets:
            # Normalize date
            normalized_date = DateNormalizerAgent.normalize_date(
                item.get("created_at") or item.get("date")
            )
            
            # Categorize
            item_category = CategorizerAgent.categorize_item(item)
            
            # Filter by category
            if item_category == category or category == "trends":
                processed_item = {
                    "source": "twitter",
                    "id": item.get("id", ""),
                    "text": item.get("text", ""),
                    "author_id": item.get("author_id", ""),
                    "username": item.get("username", ""),
                    "created_at": item.get("created_at", ""),
                    "normalized_date": normalized_date.isoformat(),
                    "timestamp": normalized_date.timestamp(),
                    "url": item.get("url", ""),
                    "retweet_count": item.get("retweet_count", 0),
                    "like_count": item.get("like_count", 0),
                    "reply_count": item.get("reply_count", 0),
                    "quote_count": item.get("quote_count", 0),
                    "entities": item.get("entities", {}),
                    "category": item_category
                }
                processed_tweets.append(processed_item)
        
        # Sort both by timestamp (newest first)
        processed_news.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        processed_tweets.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        
        logger.info(
            f"Processed category '{category}': "
            f"{len(processed_news)} news items, {len(processed_tweets)} tweets"
        )
        
        return {
            "cryptopanic": processed_news,
            "twitter": processed_tweets,
            "metadata": {
                "category": category,
                "total_news": len(processed_news),
                "total_tweets": len(processed_tweets),
                "total_items": len(processed_news) + len(processed_tweets),
                "processed_at": datetime.utcnow().isoformat() + "Z",
                "timestamp": time.time()
            }
        }
    
    @classmethod
    def process_all_sources(
        cls,
        news_items: List[Dict[str, Any]],
        tweets: List[Dict[str, Any]],
        limit_per_source: int = 50
    ) -> Dict[str, Any]:
        """
        Process all items from both sources without category filtering
        
        Returns:
            {
                "cryptopanic": [...],
                "twitter": [...],
                "metadata": {...}
            }
        """
        # Process all news
        processed_news = []
        for item in news_items[:limit_per_source]:
            normalized_date = DateNormalizerAgent.normalize_date(
                item.get("date") or item.get("published_at")
            )
            
            processed_item = {
                "source": "cryptopanic",
                "news_url": item.get("news_url", ""),
                "image_url": item.get("image_url", ""),
                "title": item.get("title", ""),
                "text": item.get("text", ""),
                "source_name": item.get("source_name", ""),
                "date": item.get("date", ""),
                "normalized_date": normalized_date.isoformat(),
                "timestamp": normalized_date.timestamp(),
                "topics": item.get("topics", []),
                "sentiment": item.get("sentiment", "Neutral"),
                "type": item.get("type", "Article"),
                "tickers": item.get("tickers", []),
                "category": CategorizerAgent.categorize_item(item)
            }
            processed_news.append(processed_item)
        
        # Process all tweets
        processed_tweets = []
        for item in tweets[:limit_per_source]:
            normalized_date = DateNormalizerAgent.normalize_date(
                item.get("created_at") or item.get("date")
            )
            
            processed_item = {
                "source": "twitter",
                "id": item.get("id", ""),
                "text": item.get("text", ""),
                "author_id": item.get("author_id", ""),
                "username": item.get("username", ""),
                "created_at": item.get("created_at", ""),
                "normalized_date": normalized_date.isoformat(),
                "timestamp": normalized_date.timestamp(),
                "url": item.get("url", ""),
                "retweet_count": item.get("retweet_count", 0),
                "like_count": item.get("like_count", 0),
                "reply_count": item.get("reply_count", 0),
                "quote_count": item.get("quote_count", 0),
                "entities": item.get("entities", {}),
                "category": CategorizerAgent.categorize_item(item)
            }
            processed_tweets.append(processed_item)
        
        # Sort by timestamp
        processed_news.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        processed_tweets.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        
        return {
            "cryptopanic": processed_news,
            "twitter": processed_tweets,
            "metadata": {
                "total_news": len(processed_news),
                "total_tweets": len(processed_tweets),
                "total_items": len(processed_news) + len(processed_tweets),
                "processed_at": datetime.utcnow().isoformat() + "Z",
                "timestamp": time.time()
            }
        }


# Keep backward compatibility alias
DataMergerAgent = DataProcessorAgent