"""Balance models for user wallet system."""

from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, Float, DateTime, Text, Index
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel, validator

from ..core.database import Base


class UserBalance(Base):
    """Database model for user balance tracking."""
    __tablename__ = "user_balances"

    user_id = Column(String(255), primary_key=True, index=True)
    balance = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BalanceTransaction(Base):
    """Database model for balance transaction history."""
    __tablename__ = "balance_transactions"

    id = Column(String(50), primary_key=True)  # transaction_id
    user_id = Column(String(255), nullable=False, index=True)
    transaction_type = Column(String(20), nullable=False)  # credit, debit
    amount = Column(Float, nullable=False)
    description = Column(Text)
    reference_id = Column(String(100))  # payment_id or other reference
    reference_type = Column(String(50))  # payment, usage, adjustment
    created_at = Column(DateTime, default=datetime.utcnow)

    # Create composite index for user queries
    __table_args__ = (
        Index('idx_user_date', 'user_id', 'created_at'),
    )


# Pydantic models for API
class BalanceResponse(BaseModel):
    """Response model for user balance."""
    user_id: str
    balance: float
    last_updated: datetime


class TransactionHistoryResponse(BaseModel):
    """Response model for transaction history."""
    id: str
    transaction_type: str
    amount: float
    description: Optional[str] = None
    reference_id: Optional[str] = None
    reference_type: Optional[str] = None
    created_at: datetime


class AddBalanceRequest(BaseModel):
    """Request model for adding balance."""
    amount: float
    
    @validator('amount')
    def validate_amount(cls, v):
        """Validate payment amount."""
        if v <= 0:
            raise ValueError('Amount must be greater than 0')
        if v > 200000:  # UPI limit
            raise ValueError('Amount exceeds limit of Rs. 2,00,000')
        return v