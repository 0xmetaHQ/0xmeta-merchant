"""
Services module - External API integrations
"""

from app.services.cryptonews import crypto_news_service
from app.services.game_x_redis import game_x_service_redis as game_x_service
from app.services.facilitator_client import facilitator_client

__all__ = [
    "crypto_news_service",
    "game_x_service",
    "facilitator_client",
]