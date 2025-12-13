from sqlalchemy import Column, String, Float, Integer, Text, ARRAY, JSON, TIMESTAMP, Boolean
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
from app.database.session import Base


class PaymentTransaction(Base):
    """X402 payment transaction logs"""
    __tablename__ = "payment_transactions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Payment info
    payment_hash = Column(String(200), unique=True, nullable=False, index=True)
    endpoint = Column(String(100), nullable=False, index=True)
    category = Column(String(50))  # Which category was accessed
    
    # Amount
    amount = Column(Float, nullable=False)
    
    # Status
    verified = Column(Boolean, default=False, index=True)
    settled = Column(Boolean, default=False, index=True)
    
    # User info
    user_identifier = Column(String(200))  # IP or wallet address
    user_wallet = Column(String(100))  # Wallet address if available
    
    # Timestamps
    created_at = Column(TIMESTAMP, default=datetime.utcnow, index=True)
    verified_at = Column(TIMESTAMP)
    settled_at = Column(TIMESTAMP)
    
    # Transaction details (JSON)
    transaction_data = Column(JSON)
    
    def __repr__(self):
        return (
            f"<PaymentTransaction(hash='{self.payment_hash[:16]}...', "
            f"category='{self.category}', verified={self.verified})>"
        )

        
