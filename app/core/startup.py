from loguru import logger
from app.database.session import init_db
from app.cache.redis_client import redis_client
from app.services.cryptonews import crypto_news_service
from app.services.game_x import game_x_service
from app.workers.cleanup import cleanup_worker
import sys
import anyio


async def startup_checks():
    """
    Perform all startup checks and initialize services
    
    Returns:
        bool: True if all checks pass, False otherwise
    """
    logger.info("=" * 60)
    logger.info("🚀 Starting 0xMeta Crypto News Aggregator")
    logger.info("=" * 60)
    
    all_checks_passed = True
    
    # # 1. Database Connection
    logger.info("\n[1/6] Checking Database Connection...")
    db_status = await init_db()

    if not db_status:
        all_checks_passed = False
    
    # 2. Redis Connection
    logger.info("\n[2/6] Checking Redis Connection...")
    redis_status = await redis_client.connect()
    if not redis_status:
        all_checks_passed = False
    
    # 3. CryptoNews API
    logger.info("\n[3/6] Checking CryptoNews API...")
    cryptonews_status = await crypto_news_service.initialize()
    if not cryptonews_status:
        all_checks_passed = False
    
    # 4. GAME X API
    logger.info("\n[4/6] Checking GAME X API...")
    gamex_status = await game_x_service.initialize()
    if not gamex_status:
        all_checks_passed = False
    
    # # 5. Payment Service
    # logger.info("\n[5/6] Initializing Payment Service...")
    # try:
    #     await payment_service.initialize()
    # except Exception as e:
    #     logger.error(f"✗ Payment service initialization failed: {str(e)}")
    #     all_checks_passed = False
    
    # 6. Cleanup Worker
    logger.info("\n[6/6] Starting Cleanup Worker...")
    try:
        cleanup_worker.start()
    except Exception as e:
        logger.error(f"✗ Cleanup worker failed to start: {str(e)}")
        all_checks_passed = False
    
    # Final Status
    logger.info("\n" + "=" * 60)
    if all_checks_passed:
        logger.info("✓ All startup checks passed successfully!")
        logger.info("✓ Application is ready to accept requests")
    else:
        logger.error("✗ Some startup checks failed")
        logger.error("✗ Application may not function correctly")
    logger.info("=" * 60 + "\n")
    
    return all_checks_passed


async def shutdown_handlers():
    """Cleanup on application shutdown"""
    logger.info("\n🛑 Shutting down application...")
    
    try:
        await crypto_news_service.close()
        logger.info("✓ CryptoNews service closed")
    except:
        pass
    
    try:
        await game_x_service.close()
        logger.info("✓ GAME X service closed")
    except:
        pass
    
    # try:
    #     await payment_service.close()
    #     logger.info("✓ Payment service closed")
    # except:
    #     pass
    
    try:
        cleanup_worker.stop()
        logger.info("✓ Cleanup worker stopped")
    except:
        pass
    
    logger.info("✓ Shutdown complete\n")