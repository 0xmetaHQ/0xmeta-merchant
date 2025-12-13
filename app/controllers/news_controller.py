"""
Controller for handling news endpoints by category
"""

from typing import Dict, Any, List
from app.services.cryptonews import crypto_news_service
from app.services.game_x import game_x_service
from app.agents.signal_transformer import SignalTransformerAgent
from app.agents.ticker_generator import TickerGeneratorAgent
from app.cache.redis_client import redis_client
from app.queue.tasks import save_category_data
from app.core.config import settings
from loguru import logger
import time


class NewsController:
    """Controller for handling category-based news endpoints"""
    
    # Predefined category tickers (can be overridden by AI)
    CATEGORY_TICKERS = {
        "btc": "BTC",
        "eth": "ETH",
        "sol": "SOL",
        "base": "ETH,OP,ARB",  # L2s
        "defi": "UNI,AAVE,MKR,CRV,SNX,COMP",
        "ai_agents": "FET,AGIX,OCEAN,TAO,RNDR",
        "rwa": "ONDO,TRU,RIO,POLYX,MPL",
        "liquidity": "UNI,CAKE,SUSHI,DYDX,BAL",
        "proof_of_work": "BTC,LTC,BCH,ETC,DASH",
        "memecoins": "DOGE,SHIB,PEPE,FLOKI,BONK",
        "stablecoins": "USDT,USDC,DAI,BUSD,FRAX",
        "nfts": "BLUR,LOOKS,APE,DEGEN",
        "gaming": "AXS,SAND,MANA,ENJ,GALA,IMX",
        "launchpad": "MANTA,SUI,SEI,APT,INJ",
        "virtuals": "VIRTUAL,GAME,AI,PRIME",
    }
    
    # Category-specific keywords for filtering
    CATEGORY_KEYWORDS = {
        "btc": ["bitcoin", "btc", "satoshi", "lightning"],
        "eth": ["ethereum", "eth", "vitalik", "eip", "gas"],
        "sol": ["solana", "sol", "phantom", "raydium"],
        "base": ["base", "coinbase", "cbeth"],
        "defi": ["defi", "dex", "amm", "yield", "lending", "borrowing"],
        "ai_agents": ["ai", "agent", "bot", "llm", "autonomous", "virtual", "virtuals"],
        "rwa": ["rwa", "real world asset", "tokenization", "securities"],
        "liquidity": ["liquidity", "volume", "tvl", "pool", "swap", "trading"],
        "macro_events": ["regulation", "sec", "fed", "etf", "government", "policy"],
        "proof_of_work": ["mining", "hashrate", "pow", "miner", "asic", "difficulty"],
        "memecoins": ["meme", "doge", "shib", "pepe", "bonk", "wif"],
        "stablecoins": ["usdt", "usdc", "dai", "stable", "tether"],
        "nfts": ["nft", "opensea", "blur", "ordinals"],
        "gaming": ["gaming", "play to earn", "p2e", "metaverse"],
        "launchpad": ["launch", "ido", "ico", "token sale"],
        "virtuals": ["virtuals", "virtual protocol", "game"],
        "trends": ["trending", "viral", "rally", "pump"],
        "other": []
    }
    
    @staticmethod
    async def get_tickers_for_category(category: str) -> str:
        """
        Get tickers for a category - uses predefined or AI-generated
        
        Args:
            category: Category name
            
        Returns:
            Comma-separated ticker string
        """
        # Check if we have predefined tickers
        if category in NewsController.CATEGORY_TICKERS:
            tickers = NewsController.CATEGORY_TICKERS[category]
            logger.info(f"✓ Using predefined tickers for {category}: {tickers}")
            return tickers
        
        # Check AI cache
        cached_tickers = TickerGeneratorAgent.get_cached_tickers(category)
        if cached_tickers:
            logger.info(f"✓ Using cached AI tickers for {category}: {cached_tickers}")
            return cached_tickers
        
        # Generate with AI
        keywords = NewsController.CATEGORY_KEYWORDS.get(category, [])
        tickers = await TickerGeneratorAgent.generate_tickers(category, keywords)
        logger.info(f"✓ Generated tickers for {category}: {tickers}")
        return tickers
    
    @staticmethod
    async def get_news_by_category(category: str) -> Dict[str, Any]:
        """
        Fetch and transform news and tweets for a specific category
        Dynamically generates tickers for unknown categories
        """
        cache_key = f"news:{category}"
        
        # Check cache
        cached = redis_client.get(cache_key)
        if cached:
            logger.info(f"✓ Returning cached data for category: {category}")
            return cached
        
        # Get keywords for this category
        keywords = NewsController.CATEGORY_KEYWORDS.get(category, [])
        
        # Get or generate tickers for this category
        tickers = await NewsController.get_tickers_for_category(category)
        
        logger.info(f"🔍 Fetching {category} news with tickers: {tickers}")
        
        # Fetch from both sources
        news = []
        tweets = []
        
        if category == "trends":
            # For trends, get trending/latest from both sources
            logger.info("Fetching trending news...")
            news = await crypto_news_service.fetch_trending_news(limit=50)
            tweets = await game_x_service.fetch_latest_tweets(max_results=50)
        else:
            # Use ticker-based fetching for CryptoNews
            logger.info(f"Fetching news for tickers: {tickers}")
            news = await crypto_news_service.fetch_ticker_news(tickers, limit=50)
            
            # For tweets, use keywords if available, otherwise fetch latest
            if keywords:
                logger.info(f"Searching tweets with keywords: {keywords}")
                tweets = await game_x_service.search_tweets_by_keywords(keywords, max_results=50)
            else:
                logger.info("Fetching latest tweets (no keywords)")
                tweets = await game_x_service.fetch_latest_tweets(max_results=50)
        
        logger.info(
            f"📊 Raw fetch results - News: {len(news)}, Tweets: {len(tweets)}"
        )
        
        # Filter items that match category (more lenient filtering)
        filtered_news = []
        for item in news:
            # For ticker-based fetches, keep all items
            # For other categories, filter by keywords
            if category == "trends" or tickers or NewsController._matches_category(item, category, keywords):
                filtered_news.append(item)
        
        filtered_tweets = []
        for item in tweets:
            if category == "trends" or NewsController._matches_category(item, category, keywords):
                filtered_tweets.append(item)
        
        logger.info(
            f"📝 After filtering - News: {len(filtered_news)}/{len(news)}, "
            f"Tweets: {len(filtered_tweets)}/{len(tweets)}"
        )
        
        # If no results, try relaxed filtering
        if len(filtered_news) == 0 and len(news) > 0:
            logger.warning(f"No news items passed filter, using all {len(news)} items")
            filtered_news = news
        
        if len(filtered_tweets) == 0 and len(tweets) > 0:
            logger.warning(f"No tweets passed filter, using all {len(tweets)} items")
            filtered_tweets = tweets
        
        # Transform to signal format using agent
        result = SignalTransformerAgent.transform_items(
            filtered_news,
            filtered_tweets,
            category
        )
        
        # Add cache TTL and ticker info
        result["metadata"]["cache_ttl"] = 3600
        result["metadata"]["tickers_used"] = tickers
        result["metadata"]["keywords_used"] = keywords
        
        # Cache result
        redis_client.set(cache_key, result)
        
        # Save to database in background
        save_category_data.send(category, result)
        
        logger.info(
            f"✅ Successfully fetched {category}: {result['metadata']['total_news']} news, "
            f"{result['metadata']['total_tweets']} tweets"
        )
        
        return result
    
    @staticmethod
    def list_available_categories(price: str, network: str) -> Dict[str, Any]:
        """
        List all available news categories with their descriptions and pricing info
        """
        return {
            "categories": [
                {"name": "btc", "aliases": ["bitcoin"], "description": "Bitcoin news and updates", "tickers": NewsController.CATEGORY_TICKERS.get("btc", "")},
                {"name": "eth", "aliases": ["ethereum"], "description": "Ethereum ecosystem", "tickers": NewsController.CATEGORY_TICKERS.get("eth", "")},
                {"name": "sol", "aliases": ["solana"], "description": "Solana ecosystem", "tickers": NewsController.CATEGORY_TICKERS.get("sol", "")},
                {"name": "base", "aliases": [], "description": "Base chain news", "tickers": NewsController.CATEGORY_TICKERS.get("base", "")},
                {"name": "defi", "aliases": [], "description": "DeFi protocols and updates", "tickers": NewsController.CATEGORY_TICKERS.get("defi", "")},
                {"name": "ai_agents", "aliases": ["ai", "agents"], "description": "AI agents and automation", "tickers": NewsController.CATEGORY_TICKERS.get("ai_agents", "")},
                {"name": "rwa", "aliases": [], "description": "Real World Assets tokenization", "tickers": NewsController.CATEGORY_TICKERS.get("rwa", "")},
                {"name": "liquidity", "aliases": [], "description": "DEX liquidity and trading", "tickers": NewsController.CATEGORY_TICKERS.get("liquidity", "")},
                {"name": "macro_events", "aliases": ["macro"], "description": "Regulation and institutional news", "tickers": "N/A"},
                {"name": "proof_of_work", "aliases": ["pow", "mining"], "description": "Mining and PoW chains", "tickers": NewsController.CATEGORY_TICKERS.get("proof_of_work", "")},
                {"name": "memecoins", "aliases": ["meme"], "description": "Meme tokens", "tickers": NewsController.CATEGORY_TICKERS.get("memecoins", "")},
                {"name": "stablecoins", "aliases": ["stable"], "description": "Stablecoin news", "tickers": NewsController.CATEGORY_TICKERS.get("stablecoins", "")},
                {"name": "nfts", "aliases": ["nft"], "description": "NFT marketplace and collections", "tickers": NewsController.CATEGORY_TICKERS.get("nfts", "")},
                {"name": "gaming", "aliases": [], "description": "Crypto gaming", "tickers": NewsController.CATEGORY_TICKERS.get("gaming", "")},
                {"name": "launchpad", "aliases": [], "description": "Token launches", "tickers": NewsController.CATEGORY_TICKERS.get("launchpad", "")},
                {"name": "virtuals", "aliases": [], "description": "Virtuals Protocol", "tickers": NewsController.CATEGORY_TICKERS.get("virtuals", "")},
                {"name": "trends", "aliases": [], "description": "Trending topics", "tickers": "All"},
                {"name": "other", "aliases": [], "description": "AI-generated tickers for any category", "tickers": "Dynamic"}
            ],
            "features": {
                "dynamic_tickers": True,
                "ai_powered": True,
                "custom_categories": "Supported - AI will generate relevant tickers"
            },
            "pricing": {
                "amount": price,
                "currency": "USDC",
                "network": network
            }
        }
    
    @staticmethod
    def _matches_category(item: Dict[str, Any], category: str, keywords: list) -> bool:
        """Check if an item matches the requested category"""
        
        # For "trends" or "other", accept all
        if category in ["trends", "other"]:
            return True
        
        # Get text content
        text = ""
        if "title" in item:
            text += item["title"].lower() + " "
        if "text" in item:
            text += item["text"].lower() + " "
        if "content" in item:
            text += item["content"].lower() + " "
        
        # Check tickers for chain-specific categories
        tickers = item.get("tickers", [])
        if tickers:
            # If item has tickers, it's likely relevant
            return True
        
        # Check keywords (relaxed matching)
        if not keywords:
            # No keywords means accept all (for ticker-based fetches)
            return True
        
        # Must match at least one keyword
        return any(keyword.lower() in text for keyword in keywords)