import sys
from loguru import logger
from app.core.config import settings


def setup_logging():
    """Configure application logging"""
    logger.remove()
    
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level=settings.LOG_LEVEL,
        colorize=True
    )
    
    logger.add(
        "logs/app_{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="7 days",
        level=settings.LOG_LEVEL,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}"
    )
    
    return logger