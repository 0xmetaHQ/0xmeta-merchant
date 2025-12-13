"""
Dramatiq worker configuration and utilities
Run this file directly to start the worker process
"""

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import CurrentMessage, Shutdown, TimeLimit, Callbacks, Pipelines, AgeLimit
from app.core.config import settings
from loguru import logger
import sys


def setup_worker():
    """Configure and setup Dramatiq worker"""
    
    # Setup Redis broker
    redis_broker = RedisBroker(url=settings.DRAMATIQ_REDIS_URL)
    
    # Add middleware
    redis_broker.add_middleware(AgeLimit(max_age=3600000))  # 1 hour max age
    redis_broker.add_middleware(TimeLimit(time_limit=300000))  # 5 min time limit
    redis_broker.add_middleware(Callbacks())
    redis_broker.add_middleware(Pipelines())
    redis_broker.add_middleware(Shutdown())
    redis_broker.add_middleware(CurrentMessage())
    
    # Set broker
    dramatiq.set_broker(redis_broker)
    
    logger.info("✓ Dramatiq worker configured successfully")
    logger.info(f"  Redis URL: {settings.DRAMATIQ_REDIS_URL}")
    logger.info("  Middleware: AgeLimit, TimeLimit, Callbacks, Pipelines")
    
    return redis_broker


def get_worker_info():
    """Get information about worker configuration"""
    return {
        "broker_url": settings.DRAMATIQ_REDIS_URL,
        "queues": ["data_storage", "data_processing"],
        "middleware": [
            "AgeLimit (1 hour)",
            "TimeLimit (5 minutes)",
            "Callbacks",
            "Pipelines",
            "Shutdown",
            "CurrentMessage"
        ]
    }


if __name__ == "__main__":
    """
    Start the Dramatiq worker
    Usage: python -m app.queue.worker
    """
    
    print("=" * 60)
    print("🚀 Starting Dramatiq Worker for 0xMeta")
    print("=" * 60)
    
    # Setup worker
    broker = setup_worker()
    
    # Import tasks to register them
    from app.queue import tasks
    
    print("\n✓ Tasks registered:")
    print("  - save_news_items")
    print("  - save_merged_data")
    print("  - process_and_categorize")
    
    print("\n✓ Queues:")
    print("  - data_storage (save operations)")
    print("  - data_processing (processing operations)")
    
    print("\n" + "=" * 60)
    print("Worker is ready to process tasks")
    print("Press Ctrl+C to stop")
    print("=" * 60 + "\n")
    
    # Note: Actual worker is started via CLI
    # dramatiq app.queue.tasks
    print("To start the worker, run:")
    print("  dramatiq app.queue.tasks -p 4 -t 4")
    print("\nOptions:")
    print("  -p 4  : 4 worker processes")
    print("  -t 4  : 4 threads per process")
    print("  -v 2  : Verbose logging (level 2)")
    
    sys.exit(0)