"""
Ticker Generator Agent
"""

import httpx
from typing import List, Optional
from loguru import logger
import json


class TickerGeneratorAgent:
    """AI agent that generates relevant crypto tickers for categories"""
    
    # Cache for generated tickers to avoid repeated API calls
    _ticker_cache = {}
    
    @classmethod
    async def generate_tickers(cls, category: str, keywords: List[str]) -> str:
        """
        Generate comma-separated tickers for a category using AI
        
        Args:
            category: Category name (e.g., "virtuals", "defi", "gaming")
            keywords: Related keywords for the category
            
        Returns:
            Comma-separated ticker string (e.g., "VIRTUAL,GAME,AI")
        """
        # Check cache first
        cache_key = category.lower()
        if cache_key in cls._ticker_cache:
            logger.info(f"✓ Using cached tickers for {category}: {cls._ticker_cache[cache_key]}")
            return cls._ticker_cache[cache_key]
        
        try:
            # Use Claude API to generate tickers
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "Content-Type": "application/json",
                        "anthropic-version": "2023-06-01"
                    },
                    json={
                        "model": "claude-sonnet-4-20250514",
                        "max_tokens": 1000,
                        "messages": [
                            {
                                "role": "user",
                                "content": f"""You are a crypto market expert. Given a category and keywords, identify the most relevant cryptocurrency tickers.

Category: {category}
Keywords: {', '.join(keywords) if keywords else 'None'}

Return ONLY a comma-separated list of 3-8 relevant crypto tickers (e.g., "BTC,ETH,SOL").
- Use official ticker symbols (BTC, ETH, SOL, etc.)
- Focus on major projects in this category
- Include both established and emerging projects
- No explanations, just the tickers

Examples:
- Category "defi" → "UNI,AAVE,MKR,CRV,SNX,COMP"
- Category "gaming" → "AXS,SAND,MANA,ENJ,GALA,IMX"
- Category "ai_agents" → "VIRTUAL,FET,AGIX,OCEAN,TAO"
- Category "virtuals" → "VIRTUAL,GAME,AI,PRIME"

Response:"""
                            }
                        ]
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    tickers = data["content"][0]["text"].strip()
                    
                    # Clean up response
                    tickers = tickers.replace('"', '').replace("'", "")
                    tickers = tickers.split('\n')[0]  # Take first line only
                    
                    # Validate format (should be comma-separated uppercase letters)
                    tickers_list = [t.strip().upper() for t in tickers.split(',')]
                    tickers_list = [t for t in tickers_list if t.isalpha() and len(t) <= 10]
                    
                    if tickers_list:
                        tickers = ','.join(tickers_list)
                        # Cache the result
                        cls._ticker_cache[cache_key] = tickers
                        logger.info(f"✓ AI generated tickers for {category}: {tickers}")
                        return tickers
                    else:
                        logger.warning(f"AI generated invalid tickers, using fallback")
                        return cls._get_fallback_tickers(category)
                else:
                    logger.error(f"Failed to generate tickers: {response.status_code}")
                    return cls._get_fallback_tickers(category)
                    
        except Exception as e:
            logger.error(f"Error generating tickers with AI: {str(e)}")
            return cls._get_fallback_tickers(category)
    
    @classmethod
    def _get_fallback_tickers(cls, category: str) -> str:
        """
        Fallback tickers when AI generation fails
        Uses predefined mappings or defaults to major coins
        """
        fallback_map = {
            "virtuals": "VIRTUAL",
            "defi": "UNI,AAVE,MKR,CRV,SNX",
            "ai_agents": "FET,AGIX,OCEAN,TAO",
            "gaming": "AXS,SAND,MANA,ENJ,GALA",
            "nfts": "BLUR,LOOKS,APE",
            "stablecoins": "USDT,USDC,DAI,BUSD",
            "memecoins": "DOGE,SHIB,PEPE,FLOKI,BONK",
            "rwa": "ONDO,TRU,RIO,POLYX",
            "liquidity": "UNI,CAKE,SUSHI,DYDX",
            "launchpad": "MANTA,SUI,SEI,APT",
        }
        
        tickers = fallback_map.get(category.lower(), "BTC,ETH,SOL,USDT,BNB,XRP,ADA,DOGE,MATIC,DOT")
        logger.info(f"✓ Using fallback tickers for {category}: {tickers}")
        return tickers
    
    @classmethod
    def get_cached_tickers(cls, category: str) -> Optional[str]:
        """Get cached tickers for a category if available"""
        return cls._ticker_cache.get(category.lower())
    
    @classmethod
    def clear_cache(cls, category: Optional[str] = None):
        """Clear ticker cache for a category or all categories"""
        if category:
            cls._ticker_cache.pop(category.lower(), None)
            logger.info(f"✓ Cleared ticker cache for {category}")
        else:
            cls._ticker_cache.clear()
            logger.info("✓ Cleared all ticker cache")
    
    @classmethod
    def preload_common_categories(cls, categories: List[str]):
        """
        Preload tickers for common categories to avoid delays
        Call this during app startup
        """
        logger.info(f"Preloading tickers for {len(categories)} categories...")
        
        # Use fallback for now, can be enhanced to use AI in background
        for category in categories:
            if category not in cls._ticker_cache:
                cls._ticker_cache[category.lower()] = cls._get_fallback_tickers(category)
        
        logger.info(f"✓ Preloaded {len(cls._ticker_cache)} category tickers")