"""
Routes module - API endpoints
"""

from app.routes.news import router as news
from app.routes.config import router as config

__all__ = ["news", "config"]