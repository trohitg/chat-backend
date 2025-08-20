"""Payment models for UPI transactions."""

from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, Float, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel, validator
import re

from ..core.database import Base


class PaymentTransaction(Base):
    """Database model for payment transactions."""
    __tablename__ = "payment_transactions"

    tracking_id = Column(String(50), primary_key=True)
    order_id = Column(String(100), nullable=False)
    payment_link_id = Column(String(100), nullable=False)
    payment_link_url = Column(String(500))
    upi_intent_url = Column(String(1000))
    payment_id = Column(String(100))  # Actual payment ID from Razorpay
    amount = Column(Float, nullable=False)
    payer_vpa = Column(String(100), nullable=False)
    beneficiary_vpa = Column(String(100), nullable=False)
    beneficiary_name = Column(String(100), nullable=False)
    description = Column(Text)
    status = Column(String(50), default="created")  # created, authorized, captured, failed, refunded
    error_message = Column(Text)  # Store error details for failed payments
    notes = Column(Text)  # JSON field for storing webhook event IDs and other metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Pydantic models for API
class VPAValidationRequest(BaseModel):
    """Request model for VPA validation."""
    vpa: str

    @validator('vpa')
    def validate_vpa_format(cls, v):
        """Validate UPI VPA format."""
        upi_pattern = r'^[a-zA-Z0-9.\-_]{2,256}@[a-zA-Z0-9]{2,64}'
        if not re.match(upi_pattern, v):
            raise ValueError('Invalid UPI VPA format')
        return v


class VPAValidationResponse(BaseModel):
    """Response model for VPA validation."""
    valid: bool
    vpa: str
    account_holder_name: Optional[str] = None
    error: Optional[str] = None


class CollectRequest(BaseModel):
    """Request model for UPI collect payments."""
    payer_vpa: str
    amount: float
    description: str
    beneficiary_vpa: str
    beneficiary_name: str

    @validator('amount')
    def validate_amount(cls, v):
        """Validate payment amount."""
        if v <= 0:
            raise ValueError('Amount must be greater than 0')
        if v > 200000:  # UPI limit
            raise ValueError('Amount exceeds UPI limit of Rs. 2,00,000')
        return v

    @validator('payer_vpa', 'beneficiary_vpa')
    def validate_vpa_format(cls, v):
        """Validate UPI VPA format."""
        upi_pattern = r'^[a-zA-Z0-9.\-_]{2,256}@[a-zA-Z0-9]{2,64}'
        if not re.match(upi_pattern, v):
            raise ValueError('Invalid UPI VPA format')
        return v


class CollectResponse(BaseModel):
    """Response model for UPI collect payments."""
    success: bool
    payment_id: Optional[str] = None
    order_id: Optional[str] = None
    status: Optional[str] = None
    message: str
    tracking_id: Optional[str] = None
    payment_link: Optional[str] = None
    upi_intent_url: Optional[str] = None


class PaymentStatusResponse(BaseModel):
    """Response model for payment status."""
    tracking_id: str
    order_id: str
    payment_id: str
    status: str
    amount: float
    payer_vpa: str
    beneficiary_vpa: str
    beneficiary_name: str
    description: str
    payment_link: Optional[str] = None
    upi_intent_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ErrorResponse(BaseModel):
    """Generic error response model."""
    message: str
    error_code: Optional[str] = None


class CreateOrderResponse(BaseModel):
    """Response model for Razorpay order creation."""
    order_id: str
    amount: float
    currency: str
    status: str
    receipt: Optional[str] = None
    key_id: str