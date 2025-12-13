"""
Database models for signal data
"""

from sqlalchemy import Column, String, Float, Integer, Text, ARRAY, JSON, TIMESTAMP, Boolean
from sqlalchemy.dialects.postgresql import UUID
from app.database.session import Base
from datetime import datetime
import uuid


class SignalItem(Base):
    """Unified signal item from CryptoNews or Twitter"""
    __tablename__ = "signal_items"
    
    # Primary identifiers
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    oxmeta_id = Column(String(100), unique=True, nullable=False, index=True)
    
    # Source info
    source = Column(String(20), nullable=False, index=True)  # 'cryptonews' or 'twitter'
    category = Column(String(50), nullable=False, index=True)
    sources = Column(ARRAY(String), nullable=False)  # Array of URLs
    
    # Content
    title = Column(Text, nullable=False)
    text = Column(Text)
    
    # Sentiment analysis
    sentiment = Column(String(20))  # bullish, bearish, neutral
    sentiment_value = Column(Float)  # 0.0 to 1.0
    
    # Classification
    feed_categories = Column(ARRAY(String))
    tokens = Column(ARRAY(String))  # ["$BTC", "$ETH"]
    
    # Author/source
    author = Column(String(200))
    
    # Timestamps
    timestamp = Column(Float, nullable=False, index=True)
    normalized_date = Column(String(200))
    
    # Additional data (JSON for flexibility)
    # ⚠️ RENAMED from 'metadata' to 'extra_data' because 'metadata' is reserved by SQLAlchemy
    extra_data = Column(JSON, name='metadata')  # Maps to 'metadata' column in DB
    
    # Database tracking
    created_at = Column(TIMESTAMP, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f"<SignalItem(oxmeta_id='{self.oxmeta_id}', source='{self.source}', category='{self.category}')>"


class CategoryFeed(Base):
    """Stores processed category feeds"""
    __tablename__ = "category_feeds"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category = Column(String(50), nullable=False, index=True)
    
    # Separate sources
    cryptonews_items = Column(JSON, nullable=False, default=list)
    twitter_items = Column(JSON, nullable=False, default=list)
    
    # Counts
    total_news = Column(Integer, default=0)
    total_tweets = Column(Integer, default=0)
    total_items = Column(Integer, default=0)
    
    # Timestamps
    last_updated = Column(Float, nullable=False, index=True)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    
    def __repr__(self):
        return (
            f"<CategoryFeed(category='{self.category}', "
            f"news={self.total_news}, tweets={self.total_tweets})>"
        )
