"""Unified Wallet API for all payment and balance operations."""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query, Request, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from ..core.database import get_db
from ..services.balance_service import BalanceService
from ..services.payment_service import PaymentService
from ..models.balance import (
    BalanceResponse, TransactionHistoryResponse, AddBalanceRequest
)
from ..models.payment import (
    CreateOrderResponse, VPAValidationRequest, VPAValidationResponse,
    CollectRequest, CollectResponse, PaymentStatusResponse
)
import structlog

logger = structlog.get_logger()

router = APIRouter(prefix="/wallet", tags=["wallet"])

# Initialize services
balance_service = BalanceService()
payment_service = PaymentService()


@router.get("/health")
async def wallet_health():
    """Wallet service health check."""
    try:
        logger.info("Wallet health check requested")
        return {
            "status": "healthy",
            "service": "wallet",
            "webhook_endpoint": "https://api.disutopia.xyz/api/v1/wallet/webhook",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error("Wallet health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "service": "wallet",
            "error": str(e)
        }


class WalletResponse(BaseModel):
    """Unified wallet response with balance and recent transactions."""
    user_id: str
    balance: float
    last_updated: datetime
    recent_transactions: List[TransactionHistoryResponse]


@router.get("/{user_id}", response_model=WalletResponse)
async def get_wallet(
    user_id: str,
    include_transactions: int = Query(5, ge=0, le=20, description="Number of recent transactions to include"),
    db: AsyncSession = Depends(get_db)
):
    """Get user wallet with balance and recent transactions."""
    try:
        logger.info("Wallet request", user_id=user_id)
        
        # Get balance
        balance_info = await balance_service.get_user_balance(user_id, db)
        
        # Get recent transactions if requested
        recent_transactions = []
        if include_transactions > 0:
            recent_transactions = await balance_service.get_transaction_history(
                user_id, db, limit=include_transactions
            )
        
        return WalletResponse(
            user_id=balance_info.user_id,
            balance=balance_info.balance,
            last_updated=balance_info.last_updated,
            recent_transactions=recent_transactions
        )
        
    except Exception as e:
        logger.error("Wallet request failed", user_id=user_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve wallet information"
        )


@router.get("/{user_id}/transactions", response_model=List[TransactionHistoryResponse])
async def get_transactions(
    user_id: str,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Get full transaction history for a user."""
    try:
        logger.info("Transaction history request", user_id=user_id, limit=limit, offset=offset)
        result = await balance_service.get_transaction_history(user_id, db, limit, offset)
        return result
    except Exception as e:
        logger.error("Transaction history failed", user_id=user_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve transaction history"
        )


@router.post("/{user_id}/add", response_model=CreateOrderResponse)
async def add_money(
    user_id: str,
    request: AddBalanceRequest,
    db: AsyncSession = Depends(get_db)
):
    """Create payment order to add money to wallet."""
    try:
        logger.info("Add money request", user_id=user_id, amount=request.amount)
        
        # Create Razorpay order for wallet top-up
        notes = {
            "payment_type": "balance_topup",
            "user_id": user_id,
            "amount": request.amount,
            "created_via": "wallet_api"
        }
        
        result = await payment_service.create_razorpay_order(request.amount, notes)
        
        if not result.get("success"):
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "Failed to create payment order")
            )
        
        logger.info("Wallet topup order created", user_id=user_id, order_id=result["order_id"])
        
        return CreateOrderResponse(
            order_id=result["order_id"],
            amount=result["amount"],
            currency=result["currency"],
            status=result["status"],
            receipt=result.get("receipt"),
            key_id=result["key_id"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Add money failed", user_id=user_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create payment: {str(e)}"
        )


@router.post("/webhook")
async def payment_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Handle Razorpay payment webhooks for wallet credits."""
    try:
        # Get raw payload for signature verification
        raw_body = await request.body()
        
        # Get signature header
        signature = request.headers.get("X-Razorpay-Signature", "")
        event_id = request.headers.get("X-Razorpay-Event-Id", "")
        
        # Parse JSON data
        webhook_data = await request.json()
        logger.info(
            "Wallet webhook received", 
            webhook_event=webhook_data.get("event"),
            event_id=event_id
        )
        
        # Verify webhook signature
        is_valid = await payment_service.verify_webhook_signature(
            raw_body.decode('utf-8'), 
            signature
        )
        
        if not is_valid:
            logger.warning("Invalid webhook signature", event_id=event_id)
            raise HTTPException(
                status_code=400,
                detail="Invalid webhook signature"
            )
        
        # Check for duplicate event (idempotency)
        is_duplicate = await payment_service.check_duplicate_event(event_id, db)
        if is_duplicate:
            logger.info("Duplicate webhook event, skipping", event_id=event_id)
            return {"status": "duplicate_event_skipped"}
        
        # Process webhook in background
        background_tasks.add_task(
            _process_wallet_webhook, 
            webhook_data,
            event_id, 
            db
        )
        
        # Return success immediately
        return {"status": "webhook_accepted"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Wallet webhook error", error=str(e))
        return {"status": "error_logged", "error": str(e)}


async def _process_wallet_webhook(webhook_data: dict, event_id: str, db: AsyncSession):
    """Process wallet-specific webhook events."""
    try:
        event = webhook_data.get("event")
        
        # Only process payment.captured events for balance credits
        if event == "payment.captured":
            payload = webhook_data.get("payload", {})
            payment_entity = payload.get("payment", {}).get("entity", {})
            
            order_id = payment_entity.get("order_id")
            payment_id = payment_entity.get("id")
            amount = payment_entity.get("amount", 0) / 100  # Convert from paise
            
            # Get order details from Razorpay
            try:
                order_details = payment_service.razorpay_client.order.fetch(order_id)
                order_notes = order_details.get("notes", {})
                payment_type = order_notes.get("payment_type")
                user_id = order_notes.get("user_id")
                
                logger.info("Processing wallet payment capture", 
                    order_id=order_id,
                    payment_type=payment_type,
                    user_id=user_id,
                    amount=amount)
                
                # Credit balance for wallet top-ups
                if payment_type == "balance_topup" and user_id and amount > 0:
                    success = await balance_service.credit_balance(
                        user_id=user_id,
                        amount=amount,
                        description=f"Wallet top-up via payment {payment_id}",
                        reference_id=payment_id,
                        reference_type="payment",
                        db=db
                    )
                    
                    if success:
                        logger.info("Wallet balance credited", 
                            user_id=user_id, 
                            amount=amount, 
                            payment_id=payment_id)
                    else:
                        logger.error("Failed to credit wallet balance", 
                            user_id=user_id, 
                            amount=amount, 
                            payment_id=payment_id)
                
            except Exception as e:
                logger.warning("Could not process wallet credit", order_id=order_id, error=str(e))
        
        # Process the main webhook through payment service
        await payment_service.process_webhook(webhook_data, event_id, db)
        
    except Exception as e:
        logger.error("Wallet webhook processing error", error=str(e), event_id=event_id)


# UPI Payment endpoints for peer-to-peer payments
@router.post("/upi/validate", response_model=VPAValidationResponse)
async def validate_vpa(request: VPAValidationRequest):
    """Validate UPI VPA."""
    try:
        result = await payment_service.validate_vpa(request.vpa)
        return result
    except Exception as e:
        logger.error("VPA validation error", error=str(e))
        raise HTTPException(status_code=500, detail="VPA validation failed")


@router.post("/upi/pay", response_model=CollectResponse)
async def create_upi_payment(
    request: CollectRequest, 
    db: AsyncSession = Depends(get_db)
):
    """Create UPI payment to another person."""
    try:
        result = await payment_service.create_payment_request(request, db)
        if not result.success:
            raise HTTPException(status_code=400, detail=result.message)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("UPI payment error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create UPI payment")


@router.get("/upi/status/{tracking_id}", response_model=PaymentStatusResponse)
async def get_upi_payment_status(
    tracking_id: str, 
    db: AsyncSession = Depends(get_db)
):
    """Get UPI payment status by tracking ID."""
    try:
        result = await payment_service.get_payment_status(tracking_id, db)
        if not result:
            raise HTTPException(status_code=404, detail="Payment not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Payment status error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve payment status")


@router.post("/{user_id}/verify-payment")
async def verify_and_credit_payment(
    user_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Verify payment with Razorpay and credit balance if successful."""
    try:
        request_data = await request.json()
        payment_id = request_data.get("payment_id")
        order_id = request_data.get("order_id")
        
        if not payment_id or not order_id:
            raise HTTPException(
                status_code=400,
                detail="Payment ID and Order ID are required"
            )
        
        logger.info("Payment verification request", 
            user_id=user_id, 
            payment_id=payment_id, 
            order_id=order_id)
        
        # Verify payment status using Razorpay APIs
        verification_result = await payment_service.verify_payment_status(payment_id, order_id)
        
        if not verification_result.get("success"):
            raise HTTPException(
                status_code=400,
                detail=verification_result.get("error", "Payment verification failed")
            )
        
        # Check if payment is captured (money received)
        if not verification_result.get("is_captured"):
            return {
                "success": False,
                "message": f"Payment not captured yet. Status: {verification_result.get('status')}",
                "payment_status": verification_result.get("status"),
                "balance_credited": False
            }
        
        # Get order notes to check payment type
        order_notes = verification_result.get("order_notes", {})
        payment_type = order_notes.get("payment_type")
        noted_user_id = order_notes.get("user_id")
        amount = verification_result.get("amount", 0)
        
        logger.info("Payment verified and captured", 
            user_id=user_id,
            payment_id=payment_id,
            payment_type=payment_type,
            amount=amount)
        
        # Credit balance for wallet top-ups
        if payment_type == "balance_topup" and noted_user_id == user_id and amount > 0:
            success = await balance_service.credit_balance(
                user_id=user_id,
                amount=amount,
                description=f"Wallet top-up via verified payment {payment_id}",
                reference_id=payment_id,
                reference_type="payment",
                db=db
            )
            
            if success:
                logger.info("Balance credited via API verification", 
                    user_id=user_id, 
                    amount=amount, 
                    payment_id=payment_id)
                
                return {
                    "success": True,
                    "message": f"Payment verified and ₹{amount} credited to wallet",
                    "payment_id": payment_id,
                    "order_id": order_id,
                    "amount_credited": amount,
                    "payment_status": verification_result.get("status"),
                    "balance_credited": True
                }
            else:
                logger.error("Failed to credit balance after verification", 
                    user_id=user_id, 
                    payment_id=payment_id)
                return {
                    "success": False,
                    "message": "Payment verified but balance credit failed",
                    "balance_credited": False
                }
        else:
            logger.warning("Payment verification mismatch", 
                payment_type=payment_type,
                noted_user_id=noted_user_id,
                requested_user_id=user_id)
            return {
                "success": False,
                "message": "Payment details do not match wallet top-up request",
                "balance_credited": False
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Payment verification API error", 
            user_id=user_id, 
            error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Payment verification failed: {str(e)}"
        )