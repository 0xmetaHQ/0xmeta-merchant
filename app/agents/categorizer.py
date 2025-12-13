"""
Enhanced Categorizer Agent - Extended categories
Categorizes crypto news and social media into specific topics
"""

from typing import Dict, Any, List
import re
from loguru import logger


class CategorizerAgent:
    """Agent for categorizing crypto news and social media updates"""
    
    # Extended category keywords mapping
    CATEGORY_KEYWORDS = {
        "btc": [
            "bitcoin", "btc", "satoshi", "lightning", "ordinals", "btc etf",
            "bitcoin mining", "bitcoin halving", "sats"
        ],
        "eth": [
            "ethereum", "eth", "vitalik", "eip", "gas", "gwei", "eth2", "ethereum 2.0",
            "beacon chain", "merge", "layer 2", "rollup", "optimism", "arbitrum"
        ],
        "sol": [
            "solana", "sol", "phantom", "raydium", "serum", "solana pay",
            "magic eden", "tensor", "jupiter"
        ],
        "base": [
            "base", "base chain", "coinbase", "cbeth", "base network"
        ],
        "defi": [
            "defi", "dex", "amm", "yield", "lending", "borrowing", "liquidity pool",
            "swap", "uniswap", "aave", "compound", "curve", "balancer", "sushiswap",
            "pancakeswap", "staking", "farming"
        ],
        "ai_agents": [
            "ai", "agent", "bot", "llm", "autonomous", "virtual", "virtuals",
            "game", "chatbot", "ai trading", "machine learning", "neural"
        ],
        "rwa": [
            "rwa", "real world asset", "tokenization", "securities", "property",
            "real estate", "tokenized", "backed", "compliant"
        ],
        "liquidity": [
            "liquidity", "volume", "tvl", "total value locked", "trading volume",
            "market depth", "orderbook", "liquidity pool", "lp", "liquidation"
        ],
        "macro_events": [
            "regulation", "sec", "fed", "federal reserve", "etf", "government",
            "policy", "institutional", "blackrock", "fidelity", "grayscale",
            "cftc", "compliance", "legal", "lawsuit", "approval", "election"
        ],
        "proof_of_work": [
            "mining", "hashrate", "pow", "proof of work", "miner", "asic",
            "difficulty", "bitcoin mining", "ethereum mining", "pool", "hash"
        ],
        "memecoins": [
            "meme", "memecoin", "doge", "dogecoin", "shib", "shiba", "pepe",
            "bonk", "wif", "floki", "community token", "viral"
        ],
        "stablecoins": [
            "stable", "stablecoin", "usdt", "usdc", "dai", "tether", "circle",
            "busd", "usdd", "frax", "algorithmic stable", "backed"
        ],
        "nfts": [
            "nft", "non-fungible", "opensea", "blur", "ordinals", "pfp",
            "collectible", "marketplace", "mint", "drop", "floor price"
        ],
        "gaming": [
            "gaming", "game", "play to earn", "p2e", "metaverse", "virtual world",
            "in-game", "axie", "sandbox", "decentraland", "gala"
        ],
        "launchpad": [
            "launch", "ido", "ico", "ieo", "token sale", "presale", "fair launch",
            "listing", "new token", "token generation"
        ],
        "virtuals": [
            "virtuals", "virtual protocol", "game by virtuals", "virtual agents"
        ],
        "trends": [
            "trending", "viral", "rally", "pump", "surge", "momentum",
            "bullish", "bearish", "sentiment", "fomo"
        ],
    }
    
    @classmethod
    def categorize_item(cls, item: Dict[str, Any]) -> str:
        """
        Categorize a single item based on content
        
        Args:
            item: News article or tweet
            
        Returns:
            Category name (e.g., 'btc', 'defi', 'ai_agents')
        """
        text = ""
        
        # Extract text content
        if "title" in item:
            text += item["title"].lower() + " "
        if "content" in item:
            text += item["content"].lower() + " "
        if "text" in item:
            text += item["text"].lower() + " "
        
        # Check tickers first for specific chains
        tickers = item.get("tickers", [])
        if tickers:
            ticker_str = " ".join(tickers).upper()
            if "BTC" in ticker_str or "BITCOIN" in ticker_str:
                return "btc"
            if "ETH" in ticker_str or "ETHEREUM" in ticker_str:
                return "eth"
            if "SOL" in ticker_str or "SOLANA" in ticker_str:
                return "sol"
        
        # Score each category
        category_scores = {}
        for category, keywords in cls.CATEGORY_KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword.lower() in text)
            category_scores[category] = score
        
        # Return category with highest score
        if max(category_scores.values()) > 0:
            best_category = max(category_scores, key=category_scores.get)
            
            # If multiple categories have same high score, prioritize specific ones
            max_score = category_scores[best_category]
            high_score_categories = [
                cat for cat, score in category_scores.items() 
                if score == max_score
            ]
            
            # Priority order for tie-breaking
            priority = ["btc", "eth", "sol", "defi", "ai_agents", "rwa"]
            for priority_cat in priority:
                if priority_cat in high_score_categories:
                    return priority_cat
            
            return best_category
        
        # Default to "other" if no matches
        return "other"
    
    @classmethod
    def categorize_items(cls, items: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Categorize multiple items into buckets
        
        Args:
            items: List of news/tweet items
            
        Returns:
            Dict with categories as keys and items as values
        """
        categorized = {}
        
        for item in items:
            category = cls.categorize_item(item)
            item["category"] = category
            
            if category not in categorized:
                categorized[category] = []
            categorized[category].append(item)
        
        logger.info(
            f"Categorized {len(items)} items: " +
            ", ".join([f"{k}={len(v)}" for k, v in categorized.items()])
        )
        
        return categorized
    
    @classmethod
    def extract_keywords(cls, text: str, limit: int = 10) -> List[str]:
        """
        Extract key terms from text for search
        
        Args:
            text: Text to extract from
            limit: Maximum keywords to return
            
        Returns:
            List of keywords
        """
        # Remove common words
        stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
            "for", "of", "with", "by", "from", "is", "are", "was", "were",
            "be", "been", "being", "have", "has", "had", "do", "does", "did",
            "will", "would", "should", "could", "may", "might", "can"
        }
        
        # Clean and split
        words = re.findall(r'\b\w+\b', text.lower())
        keywords = [w for w in words if w not in stop_words and len(w) > 3]
        
        # Get unique keywords, prioritize crypto terms
        crypto_terms = []
        other_terms = []
        
        for word in keywords:
            if any(
                term in word for term in [
                    "crypto", "token", "coin", "blockchain", "defi",
                    "bitcoin", "ethereum", "solana", "nft", "dao"
                ]
            ):
                crypto_terms.append(word)
            else:
                other_terms.append(word)
        
        # Return crypto terms first, then others
        unique_keywords = list(dict.fromkeys(crypto_terms + other_terms))
        return unique_keywords[:limit]
    
    @classmethod
    def get_all_categories(cls) -> List[str]:
        """Get list of all available categories"""
        return list(cls.CATEGORY_KEYWORDS.keys()) + ["other"]