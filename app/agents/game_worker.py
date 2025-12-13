"""
GAME X Worker Agent using official GAME SDK
This is the main agent that coordinates crypto news aggregation
"""

import logging
from typing import Dict, Any, Tuple, Optional, List
from datetime import datetime
from game_sdk.game.worker import Worker
from game_sdk.game.custom_types import Function, Argument, FunctionResultStatus
from app.services.cryptonews import crypto_news_service
from app.services.game_x import game_x_service
from app.agents.date_normalizer import DateNormalizerAgent
from app.agents.categorizer import CategorizerAgent
from app.core.config import settings
from loguru import logger


class CryptoAggregatorWorker:
    """
    GAME X Worker for crypto news aggregation
    Combines the official GAME SDK with our custom services
    """

    def __init__(self, create_worker_now: bool = True):
        """
        If create_worker_now is False, _setup_worker will not attempt to initialize the GAME SDK.
        This is useful to avoid network calls at import time.
        """
        self.api_key = settings.GAME_API_KEY
        self.worker: Optional[Worker] = None

        if create_worker_now:
            # _setup_worker catches exceptions, so this will not raise on failure
            self._setup_worker()

    def _setup_worker(self):
        """Initialize GAME SDK Worker with action space.

        This method is resilient: it logs and swallows exceptions coming from the
        SDK/network so that imports do not fail when the external service is
        unavailable (e.g., 500 responses).
        """
        try:
            # Define action space
            action_space: List[Function] = [
                Function(
                    fn_name="merge_news_and_tweets",
                    fn_description="Combine latest crypto news and X feeds into one aggregated list",
                    args=[
                        Argument(
                            name="limit",
                            type="integer",
                            description="Number of items to fetch per source (1-50)"
                        ),
                        Argument(
                            name="category",
                            type="string",
                            description="Optional category filter (trends, liquidity, agents, macro_events, proof_of_work)"
                        )
                    ],
                    executable=self.merge_news_and_tweets
                ),
                Function(
                    fn_name="search_by_keywords",
                    fn_description="Search for crypto content by specific keywords",
                    args=[
                        Argument(
                            name="keywords",
                            type="array",
                            description="List of keywords to search for"
                        ),
                        Argument(
                            name="limit",
                            type="integer",
                            description="Maximum number of results to return"
                        )
                    ],
                    executable=self.search_by_keywords
                ),
                Function(
                    fn_name="get_categorized_feed",
                    fn_description="Get feed categorized by topics",
                    args=[
                        Argument(
                            name="category",
                            type="string",
                            description="Category to filter by (bitcoin, ai_agents, defi, stablecoins, memecoins, etc.)"
                        ),
                        Argument(
                            name="limit",
                            type="integer",
                            description="Number of items to return"
                        )
                    ],
                    executable=self.get_categorized_feed
                )
            ]

            # Create GAME Worker - external call may fail; wrap it
            self.worker = Worker(
                api_key=self.api_key,
                description="Aggregates and categorizes crypto-related news and social media updates.",
                instruction=self._get_instruction(),
                get_state_fn=lambda result, state: state or {},
                action_space=action_space
            )

            logger.info("✓ GAME X Worker initialized with action space")

        except Exception as e:
            # Log full exception info but do not re-raise; leave self.worker as None.
            logger.error("❌ Failed to initialize GAME Worker (non-fatal). "
                         "Worker will be set to None. Exception: {}", e, exc_info=True)
            self.worker = None

    def _get_instruction(self) -> str:
        """Get detailed instruction for the worker"""
        return """You are an intelligent crypto news aggregation agent.

Your goal is to fetch, clean, and combine the latest crypto-related news and social posts 
from multiple data sources such as CryptoNews and Twitter (X). Perform the following tasks:

1️⃣ **Data Combination & Deduplication**:
- Combine results from all sources into a single unified feed.
- Remove any duplicate or repeated entries (check by title, text content, or URL).
- Keep only unique and most recent items based on their publication date or creation time.

2️⃣ **Categorization**:
- Automatically classify each item into one or more of the following categories based on keywords, 
context, and content relevance:
  - **Trends**: Trending content, viral posts, market momentum
  - **Liquidity**: DEX activity, trading volume, liquidity pools, market depth
  - **AI Agents**: AI, machine learning, autonomous trading, generative AI, virtual agents
  - **Macro Events**: Regulations, SEC, Fed, ETF approvals, institutional adoption
  - **Proof of Work**: Mining, hashrate, difficulty, PoW blockchains
  - **Bitcoin**: BTC, Satoshi, Lightning Network, Bitcoin-specific news
  - **DeFi**: Decentralized Finance, yield farming, staking, AMMs, lending protocols
  - **Stablecoins**: USDT, USDC, DAI, stable assets, algorithmic stablecoins
  - **Meme Coins**: DOGE, SHIB, PEPE, BONK, other viral tokens
  - **Infrastructure**: API services, developer tooling, SDKs, blockchain infrastructure
  - **RWA**: Real-world Assets Tokenization, on-chain assets, tokenized real estate
  - **Bridges**: Crosschain bridges, interoperability, multi-chain transfers
  - **DEPIN**: Decentralized Physical Infrastructure, Helium, IoTeX, Render
  - **Blockchains**: Solana, Ethereum, Avalanche, Base, Polygon, Layer-1, Layer-2

3️⃣ **Filtering Behavior**:
- When users request or filter by a category, return only items related to that category.
- Each item in the response should include: `title` (or `text`), `url`, `source`, 
  `category`, and `created_at` (ISO timestamp).

4️⃣ **Output Format**:
- Provide results as a JSON object with the key `combined`.
- Sort the array by `created_at` (newest first).
- Ensure all timestamps are in ISO format.
- Include metadata like total count, news count, and tweets count.

Your focus is on clarity, relevance, and eliminating noise. The user should see a clean, 
categorized, deduplicated, and up-to-date feed of crypto-related content.
"""

    async def merge_news_and_tweets(
        self,
        limit: int = 10,
        category: Optional[str] = None
    ) -> Tuple[FunctionResultStatus, str, Dict[str, Any]]:
        """
        Merge data from CryptoNews and X (Twitter) feeds.

        Args:
            limit: Number of items to fetch per source
            category: Optional category filter

        Returns:
            Tuple of (status, message, data)
        """
        try:
            logger.info(f"Merging feeds: limit={limit}, category={category}")

            # Fetch from both sources
            crypto_news = await crypto_news_service.fetch_trending_news(limit=limit)
            twitter_feed = await game_x_service.fetch_latest_tweets(max_results=limit)

            logger.info("📰 Fetched %s news articles and %s tweets", len(crypto_news), len(twitter_feed))

            # Normalize dates for all items
            for item in crypto_news:
                item["normalized_date"] = DateNormalizerAgent.normalize_date(
                    item.get("published_at") or item.get("date")
                )

            for item in twitter_feed:
                item["normalized_date"] = DateNormalizerAgent.normalize_date(
                    item.get("created_at") or item.get("date")
                )

            # Filter valid items
            valid_crypto_news = [
                item for item in crypto_news
                if item.get("title") and item.get("url")
            ]
            valid_twitter_feed = [
                item for item in twitter_feed
                if item.get("text") and item.get("id")
            ]

            logger.info(f"✅ Valid items: {len(valid_crypto_news)} news, {len(valid_twitter_feed)} tweets")

            # Combine items
            combined = valid_crypto_news + valid_twitter_feed

            # Categorize items
            for item in combined:
                try:
                    item["category"] = CategorizerAgent.categorize_item(item)
                except Exception as e:
                    # if categorization fails for an item, log and continue
                    logger.warning("Categorization failed for item: {} - {}", item.get("id") or item.get("url") or "<no-id>", e)

            # Filter by category if specified
            if category:
                combined = [item for item in combined if item.get("category") == category]
                logger.info(f"🔍 Filtered to {len(combined)} items in category: {category}")

            # Sort by normalized date (newest first)
            combined = sorted(
                combined,
                key=lambda x: x.get("normalized_date", "1970-01-01T00:00:00Z"),
                reverse=True
            )

            # Build response
            result = {
                "combined": combined,
                "total_items": len(combined),
                "news_count": len([i for i in combined if i.get("source") == "cryptonews"]),
                "tweets_count": len([i for i in combined if i.get("source") == "twitter"]),
                "category": category or "all",
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }

            logger.info(f"🔀 Merged {len(combined)} total items")

            return FunctionResultStatus.DONE, f"Successfully merged {len(combined)} items", result

        except Exception as e:
            logger.error(f"❌ Error merging feeds: {e}", exc_info=True)
            return FunctionResultStatus.FAILED, str(e), {}

    async def search_by_keywords(
        self,
        keywords: List[str],
        limit: int = 20
    ) -> Tuple[FunctionResultStatus, str, Dict[str, Any]]:
        """
        Search for content by specific keywords

        Args:
            keywords: List of keywords to search for
            limit: Maximum results to return

        Returns:
            Tuple of (status, message, data)
        """
        try:
            if not keywords:
                logger.warning("No keywords provided to search_by_keywords")
                return FunctionResultStatus.FAILED, "No keywords provided", {}

            logger.info(f"🔍 Searching for keywords: {', '.join(keywords)}")

            # Fetch news
            crypto_news = await crypto_news_service.fetch_latest_news(limit=50)

            # Filter news by keywords
            filtered_news = []
            for item in crypto_news:
                text = f"{item.get('title', '')} {item.get('content', '')}".lower()
                if any(keyword.lower() in text for keyword in keywords):
                    filtered_news.append(item)

            # Search tweets
            tweets = await game_x_service.search_tweets_by_keywords(keywords, max_results=limit)

            # Combine and process
            combined = filtered_news + tweets

            for item in combined:
                item["normalized_date"] = DateNormalizerAgent.normalize_date(
                    item.get("published_at") or item.get("created_at") or item.get("date")
                )
                try:
                    item["category"] = CategorizerAgent.categorize_item(item)
                except Exception:
                    item["category"] = "uncategorized"

            # Sort by date and slice to limit
            combined = sorted(
                combined,
                key=lambda x: x.get("normalized_date", "1970-01-01T00:00:00Z"),
                reverse=True
            )[:limit]

            result = {
                "combined": combined,
                "total_items": len(combined),
                "keywords": keywords,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }

            logger.info(f"✅ Found {len(combined)} items for keywords")

            return FunctionResultStatus.DONE, f"Found {len(combined)} items", result

        except Exception as e:
            logger.error(f"❌ Error searching: {e}", exc_info=True)
            return FunctionResultStatus.FAILED, str(e), {}

    async def get_categorized_feed(
        self,
        category: str,
        limit: int = 20
    ) -> Tuple[FunctionResultStatus, str, Dict[str, Any]]:
        """
        Get feed filtered by specific category

        Args:
            category: Category to filter by
            limit: Number of items to return

        Returns:
            Tuple of (status, message, data)
        """
        return await self.merge_news_and_tweets(limit=limit, category=category)


# Module-level lazy singleton: do NOT create an instance at import time.
_crypto_aggregator_worker: Optional[CryptoAggregatorWorker] = None


def get_crypto_aggregator_worker(create_if_missing: bool = True) -> Optional[CryptoAggregatorWorker]:
    """
    Return the singleton CryptoAggregatorWorker instance.

    If the worker hasn't been created yet and create_if_missing is True, this will
    attempt to create it. If GAME SDK initialization fails (network / server error),
    the function will return an instance with worker == None (the instance still exists but
    the underlying GAME Worker was not initialized), or None if instantiation itself fails.
    """
    global _crypto_aggregator_worker
    if _crypto_aggregator_worker is None and create_if_missing:
        try:
            # create but do not force a network call at import time:
            _crypto_aggregator_worker = CryptoAggregatorWorker(create_worker_now=True)
        except Exception as e:
            # In the rare case the constructor raises, log and return None
            logger.error("Failed to create CryptoAggregatorWorker: {}", e, exc_info=True)
            _crypto_aggregator_worker = None
    return _crypto_aggregator_worker


# Keep a public name but don't instantiate automatically; callers should call getter.
crypto_aggregator_worker = None
