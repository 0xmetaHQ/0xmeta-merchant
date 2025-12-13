"""
Background tasks for saving signal data to database
Uses Dramatiq for async processing
"""

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from app.core.config import settings
from app.database.session import get_session
from app.models.news import SignalItem, CategoryFeed
from typing import Dict, Any
import time
from loguru import logger
from sqlalchemy import select
import asyncio

# Setup Dramatiq broker
redis_broker = RedisBroker(url=settings.DRAMATIQ_REDIS_URL)
dramatiq.set_broker(redis_broker)


def run_async(coro):
    """Helper to run async functions in sync context"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@dramatiq.actor(queue_name="data_storage", max_retries=3)
def save_category_data(category: str, data: Dict[str, Any]):
    """
    Save processed category data with both sources
    
    Args:
        category: Category name
        data: Dict with cryptonews, twitter, and metadata keys
    """
    async def _save():
        async with get_session() as db:
            try:
                # Save category feed
                result = await db.execute(
                    select(CategoryFeed)
                    .where(CategoryFeed.category == category)
                    .order_by(CategoryFeed.last_updated.desc())
                    .limit(1)
                )
                existing = result.scalar_one_or_none()
                
                current_timestamp = time.time()
                
                cryptonews_items = data.get("cryptonews", [])
                twitter_items = data.get("twitter", [])
                
                # Update or create category feed
                if existing and (current_timestamp - existing.last_updated) < 3600:
                    existing.cryptonews_items = cryptonews_items
                    existing.twitter_items = twitter_items
                    existing.total_news = len(cryptonews_items)
                    existing.total_tweets = len(twitter_items)
                    existing.total_items = len(cryptonews_items) + len(twitter_items)
                    existing.last_updated = current_timestamp
                    logger.info(f"✓ Updated category feed for: {category}")
                else:
                    new_feed = CategoryFeed(
                        category=category,
                        cryptonews_items=cryptonews_items,
                        twitter_items=twitter_items,
                        total_news=len(cryptonews_items),
                        total_tweets=len(twitter_items),
                        total_items=len(cryptonews_items) + len(twitter_items),
                        last_updated=current_timestamp
                    )
                    db.add(new_feed)
                    logger.info(f"✓ Created new category feed for: {category}")
                
                # Save individual signal items
                all_items = cryptonews_items + twitter_items
                saved_count = 0
                
                for item in all_items:
                    # Check if item exists by oxmeta_id
                    result = await db.execute(
                        select(SignalItem).where(
                            SignalItem.oxmeta_id == item.get("oxmeta_id")
                        )
                    )
                    existing_signal = result.scalar_one_or_none()
                    
                    if not existing_signal:
                        # Extract extra fields for metadata column
                        metadata_extra = {
                            k: v for k, v in item.items()
                            if k not in [
                                'oxmeta_id', 'source', 'category', 'sources',
                                'title', 'text',
                                'sentiment', 'sentiment_value', 'feed_categories',
                                'tokens', 'author', 'timestamp', 'normalized_date'
                            ]
                        }
                        
                        signal = SignalItem(
                            oxmeta_id=item.get("oxmeta_id"),
                            source=item.get("source"),
                            category=item.get("category"),
                            sources=item.get("sources", []),
                            title=item.get("title", ""),
                            text=item.get("text"),
                            sentiment=item.get("sentiment"),
                            sentiment_value=item.get("sentiment_value"),
                            feed_categories=item.get("feed_categories", []),
                            tokens=item.get("tokens", []),
                            author=item.get("author"),
                            timestamp=item.get("timestamp"),
                            normalized_date=item.get("normalized_date"),
                            extra_data=metadata_extra  # ← Changed from metadata to extra_data
                        )
                        db.add(signal)
                        saved_count += 1
                
                await db.commit()
                logger.info(
                    f"✓ Saved {saved_count} new signal items for category: {category}"
                )
                
            except Exception as e:
                logger.error(f"❌ Error saving category data: {str(e)}")
                await db.rollback()
                raise
    
    run_async(_save())


@dramatiq.actor(queue_name="data_cleanup", max_retries=1)
def cleanup_old_signals():
    """Clean up signal items older than 24 hours"""
    async def _cleanup():
        async with get_session() as db:
            try:
                cutoff_timestamp = time.time() - (24 * 3600)  # 24 hours ago
                
                # Delete old signal items
                result = await db.execute(
                    select(SignalItem).where(SignalItem.timestamp < cutoff_timestamp)
                )
                signals_to_delete = result.scalars().all()
                for item in signals_to_delete:
                    await db.delete(item)
                
                # Delete old category feeds
                result_feeds = await db.execute(
                    select(CategoryFeed).where(CategoryFeed.last_updated < cutoff_timestamp)
                )
                feeds_to_delete = result_feeds.scalars().all()
                for item in feeds_to_delete:
                    await db.delete(item)
                
                await db.commit()
                
                deleted_signals = len(signals_to_delete)
                deleted_feeds = len(feeds_to_delete)
                
                if deleted_signals > 0 or deleted_feeds > 0:
                    logger.info(
                        f"✓ Cleaned up: {deleted_signals} signals, "
                        f"{deleted_feeds} category feeds (older than 24 hours)"
                    )
                
            except Exception as e:
                logger.error(f"❌ Error during cleanup: {str(e)}")
                await db.rollback()
                raise
    
    run_async(_cleanup())


@dramatiq.actor(queue_name="data_processing")
def refresh_cryptonews():
    """Scheduled task to refresh CryptoNews data every 1 hour"""
    logger.info("📰 Refreshing CryptoNews data...")
    # Implementation depends on your fetching strategy
    pass


@dramatiq.actor(queue_name="data_processing")
def refresh_twitter():
    """Scheduled task to refresh Twitter data every 4-5 hours"""
    logger.info("🐦 Refreshing Twitter/X data...")
    # Implementation depends on your fetching strategy
    pass