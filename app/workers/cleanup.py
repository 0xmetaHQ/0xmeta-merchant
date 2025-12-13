"""
Cleanup Worker - Scheduled job to remove old data
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database.session import get_session
from app.models.news import SignalItem, CategoryFeed
from app.models.payment import PaymentTransaction
from datetime import datetime, timedelta
from loguru import logger
from sqlalchemy import select
import time


class CleanupWorker:
    """Worker for cleaning up old data from database"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
    
    def start(self):
        """Start the cleanup scheduler"""
        # Run cleanup every hour
        self.scheduler.add_job(
            self.cleanup_old_data,
            'interval',
            hours=1,
            id='cleanup_old_data',
            name='Cleanup old database records',
            replace_existing=True
        )
        
        self.scheduler.start()
        logger.info("✓ Cleanup worker started successfully")
    
    def stop(self):
        """Stop the cleanup scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Cleanup worker stopped")
    
    @staticmethod
    async def cleanup_old_data():
        """Delete data older than 24 hours (ASYNC)"""
        async with get_session() as db:
            try:
                cutoff_timestamp = time.time() - (24 * 3600)  # 24 hours ago
                cutoff_datetime = datetime.utcnow() - timedelta(hours=24)
                
                # Delete old signal items (by timestamp)
                result_signals = await db.execute(
                    select(SignalItem).where(SignalItem.timestamp < cutoff_timestamp)
                )
                signals_to_delete = result_signals.scalars().all()
                for item in signals_to_delete:
                    await db.delete(item)
                
                # Delete old category feeds (by last_updated)
                result_feeds = await db.execute(
                    select(CategoryFeed).where(CategoryFeed.last_updated < cutoff_timestamp)
                )
                feeds_to_delete = result_feeds.scalars().all()
                for item in feeds_to_delete:
                    await db.delete(item)
                
                # Delete old payment transactions (by created_at)
                result_payments = await db.execute(
                    select(PaymentTransaction).where(PaymentTransaction.created_at < cutoff_datetime)
                )
                payments_to_delete = result_payments.scalars().all()
                for item in payments_to_delete:
                    await db.delete(item)
                
                await db.commit()
                
                deleted_signals = len(signals_to_delete)
                deleted_feeds = len(feeds_to_delete)
                deleted_payments = len(payments_to_delete)
                
                if deleted_signals > 0 or deleted_feeds > 0 or deleted_payments > 0:
                    logger.info(
                        f"✓ Cleaned up: {deleted_signals} signals, "
                        f"{deleted_feeds} feeds, {deleted_payments} payments (>24hrs old)"
                    )
                
            except Exception as e:
                logger.error(f"❌ Error during cleanup: {str(e)}")
                await db.rollback()
                raise


cleanup_worker = CleanupWorker()