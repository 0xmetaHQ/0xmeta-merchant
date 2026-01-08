"""
Controller for handling news endpoints by category
"""

from typing import Dict, Any, List, Optional
from app.services.rss import rss_news_service
from app.services.game_x import game_x_service
from app.agents.signal_transformer import SignalTransformerAgent
from app.agents.ticker_generator import TickerGeneratorAgent
from app.cache.redis_client import redis_client
from app.queue.tasks import save_category_data
from app.database.session import get_session
from sqlalchemy import select
from app.models.news import CategoryFeed
from app.core.config import settings
from loguru import logger
import time


class NewsController:
    """Controller for handling category-based news endpoints""" 
    
    @staticmethod
    def _normalize_category(category: str) -> str:
        normalized = category.lower().strip()
        
        if normalized in settings.CATEGORY_ALIASES:
            return settings.CATEGORY_ALIASES[normalized]
        
        if normalized in settings.VALID_CATEGORIES:
            return normalized
        
        logger.warning(f"Invalid category '{category}', defaulting to 'other'")
        return "other"
    
    @staticmethod
    async def get_tickers_for_category(category: str) -> str:
        """Get tickers for a category - uses predefined or AI-generated"""
        category = NewsController._normalize_category(category)
        
        if category in settings.CATEGORY_TICKERS:
            tickers = settings.CATEGORY_TICKERS[category]
            logger.info(f"✓ Using predefined tickers for {category}: {tickers}")
            return tickers
        
        cached_tickers = TickerGeneratorAgent.get_cached_tickers(category)
        if cached_tickers:
            logger.info(f"✓ Using cached AI tickers for {category}: {cached_tickers}")
            return cached_tickers
        
        keywords = settings.CATEGORY_KEYWORDS.get(category, [])
        tickers = await TickerGeneratorAgent.generate_tickers(category, keywords)
        logger.info(f"✓ Generated tickers for {category}: {tickers}")
        return tickers
    
    @staticmethod
    async def get_news_by_category(
        category: str,
        clean_content: bool = True,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Fetch and transform news and tweets for a specific category
        Uses RSS API
        """
        # Normalize category
        category = NewsController._normalize_category(category)
        
        # Include limit in cache key
        cache_key = f"news:{category}:{'clean' if clean_content else 'raw'}"
        if limit:
            cache_key += f":limit{limit}"
        
        # Check cache
        cached = redis_client.get(cache_key)
        if cached:
            logger.info(f"✓ Returning cached data for category: {category}")
            return cached
        
        # Check Database
        async with get_session() as db:
            result = await db.execute(
                select(CategoryFeed)
                .where(CategoryFeed.category == category)
                .order_by(CategoryFeed.last_updated.desc())
                .limit(1)
            )
            existing_feed = result.scalar_one_or_none()
            
            if existing_feed:
                age = time.time() - existing_feed.last_updated
                if age < settings.NEWS_CACHE_DURATION:
                    logger.info(f"✓ Found fresh data in DB for {category} (age: {int(age)}s)")
                    
                    data = {
                        "category": existing_feed.category,
                        "metadata": {
                            "total_news": existing_feed.total_news,
                            "total_tweets": existing_feed.total_tweets,
                            "total_items": existing_feed.total_items,
                            "last_updated": existing_feed.last_updated
                        },
                        "cryptonews": existing_feed.cryptonews_items,
                        "twitter": existing_feed.twitter_items
                    }
                    
                    if limit:
                        data["cryptonews"] = data["cryptonews"][:limit]
                        data["twitter"] = data["twitter"][:limit]
                    
                    redis_client.set(cache_key, data)
                    return data
                else:
                    logger.info(f"⌛ DB data for {category} is stale (age: {int(age)}s), fetching fresh...")
            else:
                logger.info(f"∅ No DB data found for {category}, fetching fresh...")
        
        # Get keywords and tickers
        keywords = settings.CATEGORY_KEYWORDS.get(category, [])
        tickers = await NewsController.get_tickers_for_category(category)
        
        logger.info(f"🔍 Fetching {category} news with tickers: {tickers}, keywords: {keywords}")
        
        # Fetch from sources
        news = []
        tweets = []
        
        fetch_limit = limit if limit else 50
        
        if category == "trends":
            logger.info("Fetching trending news...")
            
            # RSS API 
            news = await rss_news_service.fetch_news(limit=fetch_limit)
            
            tweets = await game_x_service.fetch_latest_tweets(max_results=50)
            
        else:
            # Ticker-based fetching
            logger.info(f"Fetching news for tickers: {tickers}")
            
            # Filter by tickers/keywords client-side
            if news:
                ticker_list = [t.strip() for t in tickers.split(",")]
                news = [
                    item for item in all_news
                    if any(ticker.lower() in item["text"].lower() for ticker in ticker_list)
                    or any(kw.lower() in item["text"].lower() for kw in keywords)
                    or any(ticker in item.get("tickers", []) for ticker in ticker_list)
                ][:fetch_limit]
            
            # Fallback to RSS if no matches
            if not news:
                all_rss_news = await rss_news_service.fetch_news(limit=100)
                
                ticker_list = [t.strip() for t in tickers.split(",")]
                news = [
                    item for item in all_rss_news
                    if any(ticker.lower() in item["text"].lower() for ticker in ticker_list)
                    or any(kw.lower() in item["text"].lower() for kw in keywords)
                    or any(ticker in item.get("tickers", []) for ticker in ticker_list)
                ][:fetch_limit]
            
            # Fetch tweets
            logger.info(f"Fetching tweets from whitelisted accounts with keyword filter: {keywords}")
            if keywords:
                tweets = await game_x_service.search_tweets_by_keywords(keywords, max_results=50)
            else:
                tweets = await game_x_service.fetch_latest_tweets(max_results=50)
        
        logger.info(f"📊 Raw fetch results - News: {len(news)}, Tweets: {len(tweets)}")
        
        # Filter tweets by category
        filtered_tweets = []
        for item in tweets:
            if category == "trends" or NewsController._matches_category(item, category, keywords):
                filtered_tweets.append(item)
        
        logger.info(
            f"📝 After filtering - News: {len(news)}, "
            f"Tweets: {len(filtered_tweets)}/{len(tweets)}"
        )
        
        # If no results, use relaxed filtering
        if len(filtered_tweets) == 0 and len(tweets) > 0:
            logger.warning(f"No tweets passed filter, using all {len(tweets)} tweets")
            filtered_tweets = tweets
        
        # Apply limit before transformation
        if limit:
            news = news[:limit]
            filtered_tweets = filtered_tweets[:limit]
        
        # Transform items
        result = await SignalTransformerAgent.transform_items(
            news,
            filtered_tweets,
            category,
            clean_content=clean_content
        )
        
        # Cache result
        redis_client.set(cache_key, result)
        
        # Save to database (only if full fetch, not preview)
        if not limit:
            save_category_data.send(category, result)
        
        logger.info(
            f"✅ Successfully fetched {category}: {result['metadata']['total_news']} news, "
            f"{result['metadata']['total_tweets']} tweets"
        )
        
        return result
    
    @staticmethod
    def list_available_categories(price: str, network: str) -> Dict[str, Any]:
        """List all available news categories from VALID_CATEGORIES"""
        categories_info = []
        
        for cat in settings.VALID_CATEGORIES:
            if cat in settings.CATEGORY_ALIASES.values():
                continue
            
            aliases = [k for k, v in settings.CATEGORY_ALIASES.items() if v == cat]
            
            categories_info.append({
                "name": cat,
                "aliases": aliases,
                "description": NewsController._get_category_description(cat),
                "tickers": settings.CATEGORY_TICKERS.get(cat, "Dynamic")
            })
        
        return {
            "categories": categories_info,
            "features": {
                "dynamic_tickers": True,
                "ai_powered": True,
                "content_cleaning": True,
                "whitelisted_accounts_only": True,
                "custom_categories": "Supported via 'other' category"
            },
            "pricing": {
                "amount": price,
                "currency": "USDC",
                "network": network
            }
        }
    
    @staticmethod
    def _get_category_description(category: str) -> str:
        """Get human-readable description for category"""
        descriptions = {
            "btc": "Bitcoin news and updates",
            "eth": "Ethereum ecosystem",
            "sol": "Solana ecosystem",
            "base": "Base chain news",
            "defi": "DeFi protocols and updates",
            "ai_agents": "AI agents and automation",
            "aptos": "Aptos blockchain",
            "rwa": "Real World Assets tokenization",
            "liquidity": "DEX liquidity and trading",
            "macro_events": "Regulation and institutional news",
            "proof_of_work": "Mining and PoW chains",
            "memecoins": "Meme tokens",
            "stablecoins": "Stablecoin news",
            "nfts": "NFT marketplace and collections",
            "gaming": "Crypto gaming",
            "launchpad": "Token launches",
            "virtuals": "Virtuals Protocol",
            "trends": "Trending topics",
            "ondo": "Ondo Finance",
            "perp_dexs": "Perpetual DEX protocols",
            "crypto": "General crypto news",
            "dats": "Decentralized data and storage",
            "hyperliquid": "Hyperliquid protocol",
            "machine_learning": "ML and AI in crypto",
            "ripple": "Ripple and XRP",
            "tech": "Technology and innovation",
            "whale_movement": "Large whale transactions",
            "other": "AI-generated tickers for custom topics"
        }
        return descriptions.get(category, "Crypto news category")
    
    @staticmethod
    def _matches_category(item: Dict[str, Any], category: str, keywords: list) -> bool:
        """Check if an item matches the requested category"""
        
        if category in ["trends", "other"]:
            return True
        
        text = ""
        if "title" in item:
            text += item["title"].lower() + " "
        if "text" in item:
            text += item["text"].lower() + " "
        if "content" in item:
            text += item["content"].lower() + " "
        
        tickers = item.get("tickers", [])
        if tickers:
            return True
        
        if not keywords:
            return True
        
        return any(keyword.lower() in text for keyword in keywords)