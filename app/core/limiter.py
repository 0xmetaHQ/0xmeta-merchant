from slowapi import Limiter
from slowapi.util import get_remote_address
from app.core.config import settings
import redis

# Initialize Redis connection for limiter storage if needed, 
# but slowapi usually takes a string URL.
# We will use the REDIS_URL from settings.

def get_limiter_storage_url():
    return settings.REDIS_URL

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.REDIS_URL,
    strategy="fixed-window"
)
