"""
Controller for handling news endpoints by category
Updated to support async content cleaning and use VALID_CATEGORIES
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
    
    CATEGORY_TICKERS = {
        "btc": "BTC",
        "eth": "ETH",
        "sol": "SOL",
        "base": "ETH,OP,ARB",
        "defi": "UNI,AAVE,MKR,CRV,SNX,COMP",
        "ai_agents": "FET,AGIX,OCEAN,TAO,RNDR",
        "aptos": "APT",
        "rwa": "ONDO,TRU,RIO,POLYX,MPL",
        "liquidity": "UNI,CAKE,SUSHI,DYDX,BAL",
        "macro_events": "BTC,ETH",
        "proof_of_work": "BTC,LTC,BCH,ETC,DASH",
        "memecoins": "DOGE,SHIB,PEPE,FLOKI,BONK",
        "stablecoins": "USDT,USDC,DAI,BUSD,FRAX",
        "nfts": "BLUR,LOOKS,APE,DEGEN",
        "gaming": "AXS,SAND,MANA,ENJ,GALA,IMX",
        "launchpad": "MANTA,SUI,SEI,APT,INJ",
        "virtuals": "VIRTUAL,GAME,AI,PRIME",
        "ondo": "ONDO",
        "perp_dexs": "DYDX,GMX,GNS,PERP",
        "crypto": "BTC,ETH,SOL",
        "dats": "TAO,FET,AGIX",
        "hyperliquid": "HYPE",
        "machine_learning": "TAO,FET,AGIX,OCEAN",
        "ripple": "XRP",
        "tech": "BTC,ETH",
        "whale_movement": "BTC,ETH,SOL",
    }
    
    CATEGORY_KEYWORDS = {
        "btc": ["bitcoin", "btc", "satoshi", "lightning"],
        "eth": ["ethereum", "eth", "vitalik", "eip", "gas"],
        "sol": ["solana", "sol", "phantom", "raydium"],
        "base": ["base", "coinbase", "cbeth"],
        "defi": ["defi", "dex", "amm", "yield", "lending", "borrowing"],
        "ai_agents": ["ai", "agent", "bot", "llm", "autonomous", "virtual"],
        "aptos": ["aptos", "apt", "move"],
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
        "ondo": ["ondo", "ondo finance", "tokenized"],
        "perp_dexs": ["perpetual", "perp", "futures", "leverage"],
        "crypto": ["crypto", "cryptocurrency", "blockchain"],
        "dats": ["data", "decentralized", "storage"],
        "hyperliquid": ["hyperliquid", "hype"],
        "machine_learning": ["machine learning", "ml", "neural", "training"],
        "ripple": ["ripple", "xrp"],
        "tech": ["technology", "innovation", "protocol"],
        "whale_movement": ["whale", "large transfer", "big move"],
        "other": []
    }
    
    @staticmethod
    def _normalize_category(category: str) -> str:
        """Normalize category using settings.CATEGORY_ALIASES"""
        normalized = category.lower().strip()
        
        # Check if it's an alias
        if normalized in settings.CATEGORY_ALIASES:
            return settings.CATEGORY_ALIASES[normalized]
        
        # Check if it's already valid
        if normalized in settings.VALID_CATEGORIES:
            return normalized
        
        # Default to 'other'
        logger.warning(f"Invalid category '{category}', defaulting to 'other'")
        return "other"
    
    @staticmethod
    async def get_tickers_for_category(category: str) -> str:
        """Get tickers for a category - uses predefined or AI-generated"""
        # Normalize category first
        category = NewsController._normalize_category(category)
        
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
    async def get_news_by_category(
        category: str,
        clean_content: bool = True
    ) -> Dict[str, Any]:
        """
        Fetch and transform news and tweets for a specific category
        
        Args:
            category: Category name (will be normalized to VALID_CATEGORIES)
            clean_content: Whether to clean content with AI (default: True)
        """
        # Normalize category
        category = NewsController._normalize_category(category)
        
        cache_key = f"news:{category}:{'clean' if clean_content else 'raw'}"
        
        # Check cache
        cached = redis_client.get(cache_key)
        if cached:
            logger.info(f"✓ Returning cached data for category: {category}")
            return cached
        
        # Check Database (Neon/Postgres)
        from app.database.session import get_session
        from sqlalchemy import select
        from app.models.news import CategoryFeed
        
        async with get_session() as db:
            result = await db.execute(
                select(CategoryFeed)
                .where(CategoryFeed.category == category)
                .order_by(CategoryFeed.last_updated.desc())
                .limit(1)
            )
            existing_feed = result.scalar_one_or_none()
            
            if existing_feed:
                # Check freshness
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
                    
                    # Hydrate Redis
                    redis_client.set(cache_key, data)
                    
                    return data
                else:
                    logger.info(f"⌛ DB data for {category} is stale (age: {int(age)}s), fetching fresh...")
            else:
                logger.info(f"∅ No DB data found for {category}, fetching fresh...")
        
        # Get keywords and tickers
        keywords = NewsController.CATEGORY_KEYWORDS.get(category, [])
        tickers = await NewsController.get_tickers_for_category(category)
        
        logger.info(f"🔍 Fetching {category} news with tickers: {tickers}, keywords: {keywords}")
        
        # Fetch from both sources
        news = []
        tweets = []
        
        if category == "trends":
            logger.info("Fetching trending news...")
            news = await crypto_news_service.fetch_trending_news(limit=50)
            tweets = await game_x_service.fetch_latest_tweets(max_results=50)
        else:
            # Use ticker-based fetching for CryptoNews
            logger.info(f"Fetching news for tickers: {tickers}")
            news = await crypto_news_service.fetch_ticker_news(tickers, limit=50)
            
            # For tweets, ALWAYS fetch from whitelisted accounts and filter by keywords
            logger.info(f"Fetching tweets from whitelisted accounts with keyword filter: {keywords}")
            if keywords:
                tweets = await game_x_service.search_tweets_by_keywords(keywords, max_results=50)
            else:
                # Even without keywords, fetch from whitelisted accounts only
                tweets = await game_x_service.fetch_latest_tweets(max_results=50)
        
        logger.info(
            f"📊 Raw fetch results - News: {len(news)}, Tweets: {len(tweets)}"
        )
        
        # Filter items that match category
        filtered_news = []
        for item in news:
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
        
        # If no results, use relaxed filtering
        if len(filtered_news) == 0 and len(news) > 0:
            logger.warning(f"No news items passed filter, using all {len(news)} items")
            filtered_news = news
        
        if len(filtered_tweets) == 0 and len(tweets) > 0:
            logger.warning(f"No tweets passed filter, using all {len(tweets)} items")
            filtered_tweets = tweets
        
        # Transform items (async)
        result = await SignalTransformerAgent.transform_items(
            filtered_news,
            filtered_tweets,
            category,
            clean_content=clean_content
        )
        
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
        """List all available news categories from VALID_CATEGORIES"""
        categories_info = []
        
        for cat in settings.VALID_CATEGORIES:
            # Get canonical name (skip aliases)
            if cat in settings.CATEGORY_ALIASES.values():
                continue
            
            # Find aliases
            aliases = [k for k, v in settings.CATEGORY_ALIASES.items() if v == cat]
            
            categories_info.append({
                "name": cat,
                "aliases": aliases,
                "description": NewsController._get_category_description(cat),
                "tickers": NewsController.CATEGORY_TICKERS.get(cat, "Dynamic")
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
        
        # "trends" and "other" accept all
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
        
        # Check tickers (strong signal)
        tickers = item.get("tickers", [])
        if tickers:
            return True
        
        # No keywords means accept all (for ticker-based fetches)
        if not keywords:
            return True
        
        # Must match at least one keyword
        return any(keyword.lower() in text for keyword in keywords)