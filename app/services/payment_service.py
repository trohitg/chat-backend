"""UPI Payment service using Razorpay integration."""

import uuid
import razorpay
import hmac
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional
from urllib.parse import quote
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, exists

from ..core.config import settings
from ..models.payment import (
    PaymentTransaction, VPAValidationResponse, CollectResponse, 
    PaymentStatusResponse, CollectRequest
)
import structlog

logger = structlog.get_logger()


class PaymentService:
    """Service class for handling UPI payments."""
    
    def __init__(self):
        """Initialize Razorpay client."""
        self.razorpay_client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )
        self.razorpay_client.set_app_details({
            "title": settings.PROJECT_NAME, 
            "version": settings.API_VERSION
        })
        self.default_mobile = "9987582423"  # Default mobile for SMS notifications

    async def validate_vpa(self, vpa: str) -> VPAValidationResponse:
        """Validate UPI VPA format and structure."""
        try:
            logger.info("Validating VPA", vpa=vpa)
            
            # Basic format validation (already done by Pydantic)
            if "@" not in vpa or len(vpa.split("@")) != 2:
                return VPAValidationResponse(
                    valid=False,
                    vpa=vpa,
                    error="Invalid VPA format"
                )
            
            # In production, you might want to use Razorpay VPA validation API
            # For now, we'll do basic validation
            logger.info("VPA validated successfully", vpa=vpa)
            return VPAValidationResponse(
                valid=True,
                vpa=vpa,
                account_holder_name="Account Holder"
            )
            
        except Exception as e:
            logger.error("VPA validation error", vpa=vpa, error=str(e))
            return VPAValidationResponse(
                valid=False,
                vpa=vpa,
                error=f"Validation error: {str(e)}"
            )

    def generate_upi_intent_url(
        self, 
        payee_vpa: str, 
        payee_name: str, 
        amount: float, 
        transaction_reference: str, 
        transaction_note: str
    ) -> str:
        """
        Generate UPI intent URL according to NPCI specifications.
        
        Format: upi://pay?pa=<payee_vpa>&pn=<payee_name>&tr=<transaction_reference>&am=<amount>&cu=INR&tn=<transaction_note>
        
        Args:
            payee_vpa: Beneficiary VPA (mandatory)
            payee_name: Beneficiary name (mandatory)  
            amount: Transaction amount
            transaction_reference: Transaction reference ID (mandatory for merchants)
            transaction_note: Transaction description
            
        Returns:
            UPI intent URL string
        """
        try:
            # URL encode parameters to handle special characters
            params = [
                f"pa={quote(payee_vpa)}",  # Payee address (mandatory)
                f"pn={quote(payee_name)}",  # Payee name (mandatory)
                f"tr={quote(transaction_reference)}",  # Transaction reference (mandatory for merchants)
                f"am={amount}",  # Amount 
                "cu=INR",  # Currency (INR for India)
                f"tn={quote(transaction_note)}"  # Transaction note
            ]
            
            upi_url = f"upi://pay?{'&'.join(params)}"
            
            logger.info(
                "UPI intent URL generated", 
                payee_vpa=payee_vpa, 
                amount=amount,
                transaction_reference=transaction_reference
            )
            
            return upi_url
            
        except Exception as e:
            logger.error("Failed to generate UPI intent URL", error=str(e))
            return ""

    async def create_payment_request(
        self, 
        request: CollectRequest, 
        db: AsyncSession
    ) -> CollectResponse:
        """Create UPI payment request using Razorpay Payment Links."""
        try:
            logger.info(
                "Creating payment request", 
                payer_vpa=request.payer_vpa, 
                amount=request.amount
            )
            
            # Generate unique identifiers
            tracking_id = f"track_{uuid.uuid4().hex[:8]}"
            receipt_id = f"receipt_{uuid.uuid4().hex[:12]}"
            
            # Step 1: Create Razorpay order
            order_data = {
                "amount": int(request.amount * 100),  # Convert to paise
                "currency": "INR",
                "receipt": receipt_id,
                "notes": {
                    "payer_vpa": request.payer_vpa,
                    "beneficiary_vpa": request.beneficiary_vpa,
                    "beneficiary_name": request.beneficiary_name,
                    "description": request.description,
                    "tracking_id": tracking_id
                }
            }
            
            logger.info("Creating Razorpay order", amount=request.amount)
            order = self.razorpay_client.order.create(order_data)
            logger.info("Order created successfully", order_id=order['id'])
            
            # Step 2: Create Payment Link with UPI-only checkout
            payment_link_data = {
                "amount": int(request.amount * 100),  # Amount in paise
                "currency": "INR", 
                "description": request.description,
                "customer": {
                    "name": request.beneficiary_name,
                    "contact": self.default_mobile,
                    "email": "payer@example.com",  # Optional
                },
                "notify": {
                    "sms": True,  # Enable SMS notification
                    "email": False
                },
                "notes": {
                    "payer_vpa": request.payer_vpa,
                    "beneficiary_vpa": request.beneficiary_vpa,
                    "beneficiary_name": request.beneficiary_name,
                    "tracking_id": tracking_id
                },
                "options": {
                    "checkout": {
                        "method": {
                            "upi": True,
                            "card": False,
                            "netbanking": False,
                            "wallet": False
                        }
                    }
                }
            }
            
            logger.info("Creating UPI payment link", payer_vpa=request.payer_vpa)
            payment_link = self.razorpay_client.payment_link.create(payment_link_data)
            logger.info("UPI payment link created", payment_link_id=payment_link['id'])
            
            # Step 3: Generate UPI intent URL for direct app invocation
            upi_intent_url = self.generate_upi_intent_url(
                payee_vpa=request.beneficiary_vpa,
                payee_name=request.beneficiary_name,
                amount=request.amount,
                transaction_reference=tracking_id,
                transaction_note=request.description
            )
            
            # Step 4: Store payment record in database
            payment_record = PaymentTransaction(
                tracking_id=tracking_id,
                order_id=order["id"],
                payment_link_id=payment_link["id"],
                payment_link_url=payment_link.get("short_url", ""),
                upi_intent_url=upi_intent_url,
                amount=request.amount,
                payer_vpa=request.payer_vpa,
                beneficiary_vpa=request.beneficiary_vpa,
                beneficiary_name=request.beneficiary_name,
                description=request.description,
                status=payment_link.get("status", "created"),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.add(payment_record)
            await db.commit()
            
            logger.info("Payment record saved", tracking_id=tracking_id)
            
            return CollectResponse(
                success=True,
                payment_id=payment_link["id"],
                order_id=order["id"],
                status=payment_link.get("status", "created"),
                message=f"UPI payment request created for {request.beneficiary_name}. Use UPI intent to pay directly via your UPI app.",
                tracking_id=tracking_id,
                payment_link=payment_link.get("short_url"),
                upi_intent_url=upi_intent_url
            )
            
        except Exception as e:
            error_msg = str(e)
            logger.error("Payment request error", error=error_msg)
            
            # Check for specific error patterns
            if "authentication" in error_msg.lower() or "unauthorized" in error_msg.lower():
                return CollectResponse(
                    success=False,
                    message="Payment gateway authentication failed. Please check configuration."
                )
            elif "bad request" in error_msg.lower() or "invalid" in error_msg.lower():
                return CollectResponse(
                    success=False,
                    message=f"Invalid payment request: {error_msg}"
                )
            else:
                return CollectResponse(
                    success=False,
                    message=f"Failed to create payment request: {error_msg}"
                )

    async def get_payment_status(
        self, 
        tracking_id: str, 
        db: AsyncSession
    ) -> Optional[PaymentStatusResponse]:
        """Get payment status by tracking ID."""
        try:
            # Query payment record from database
            result = await db.execute(
                select(PaymentTransaction).where(
                    PaymentTransaction.tracking_id == tracking_id
                )
            )
            payment_record = result.scalar_one_or_none()
            
            if not payment_record:
                return None
            
            return PaymentStatusResponse(
                tracking_id=payment_record.tracking_id,
                order_id=payment_record.order_id,
                payment_id=payment_record.payment_link_id,
                status=payment_record.status,
                amount=payment_record.amount,
                payer_vpa=payment_record.payer_vpa,
                beneficiary_vpa=payment_record.beneficiary_vpa,
                beneficiary_name=payment_record.beneficiary_name,
                description=payment_record.description,
                payment_link=payment_record.payment_link_url,
                upi_intent_url=payment_record.upi_intent_url,
                created_at=payment_record.created_at,
                updated_at=payment_record.updated_at
            )
            
        except Exception as e:
            logger.error("Status check error", tracking_id=tracking_id, error=str(e))
            return None

    async def verify_webhook_signature(self, body: str, signature: str) -> bool:
        """
        Verify Razorpay webhook signature using HMAC SHA256.
        
        Args:
            body: Raw webhook request body as string
            signature: X-Razorpay-Signature header value
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            if not signature:
                logger.warning("Missing webhook signature")
                return False
            
            # Generate expected signature
            expected_signature = hmac.new(
                key=settings.RAZORPAY_WEBHOOK_SECRET.encode('utf-8'),
                msg=body.encode('utf-8'),
                digestmod=hashlib.sha256
            ).hexdigest()
            
            # Compare signatures (use hmac.compare_digest for timing attack protection)
            is_valid = hmac.compare_digest(expected_signature, signature)
            
            if not is_valid:
                logger.warning("Invalid webhook signature", 
                    expected=expected_signature[:10] + "...", 
                    received=signature[:10] + "...")
            
            return is_valid
            
        except Exception as e:
            logger.error("Webhook signature verification error", error=str(e))
            return False
    
    async def check_duplicate_event(self, event_id: str, db: AsyncSession) -> bool:
        """
        Check if webhook event has already been processed (idempotency).
        
        Args:
            event_id: X-Razorpay-Event-Id header value
            db: Database session
            
        Returns:
            True if event is duplicate, False otherwise
        """
        try:
            if not event_id:
                return False
            
            # Check if event_id exists in processed_webhook_events table
            # For simplicity, storing in payment_transaction notes field
            result = await db.execute(
                select(exists().where(
                    PaymentTransaction.notes.like(f'%"event_id": "{event_id}"%')
                ))
            )
            is_duplicate = result.scalar()
            
            return is_duplicate
            
        except Exception as e:
            logger.error("Duplicate check error", error=str(e))
            return False

    async def process_webhook(self, webhook_data: Dict[str, Any], event_id: str, db: AsyncSession) -> bool:
        """
        Process Razorpay webhook data with enhanced event handling.
        
        Supported events:
        - payment.captured: Payment successful
        - payment.failed: Payment failed  
        - payment.authorized: Payment authorized (for two-step payments)
        - order.paid: Order fully paid
        - refund.created: Refund initiated
        - refund.processed: Refund completed
        """
        try:
            event = webhook_data.get("event")
            payload = webhook_data.get("payload", {})
            
            logger.info("Processing webhook", webhook_event=event, event_id=event_id)
            
            # Extract entity based on event type
            if "payment" in event:
                entity = payload.get("payment", {}).get("entity", {})
            elif "order" in event:
                entity = payload.get("order", {}).get("entity", {})
            elif "refund" in event:
                entity = payload.get("refund", {}).get("entity", {})
            else:
                entity = {}
            
            # Handle different event types
            if event == "payment.captured":
                # Payment successful
                await self._handle_payment_captured(entity, event_id, db)
                
            elif event == "payment.failed":
                # Payment failed
                await self._handle_payment_failed(entity, event_id, db)
                
            elif event == "payment.authorized":
                # Payment authorized (for two-step payments)
                await self._handle_payment_authorized(entity, event_id, db)
                
            elif event == "order.paid":
                # Order fully paid
                await self._handle_order_paid(entity, event_id, db)
                
            elif event == "refund.created":
                # Refund initiated
                await self._handle_refund_created(entity, event_id, db)
                
            elif event == "refund.processed":
                # Refund completed
                await self._handle_refund_processed(entity, event_id, db)
                
            else:
                logger.info("Unhandled webhook event type", event=event)
            
            return True
            
        except Exception as e:
            logger.error("Webhook processing error", error=str(e), event_id=event_id)
            return False
    
    async def _handle_payment_captured(self, payment_entity: Dict, event_id: str, db: AsyncSession):
        """Handle successful payment capture."""
        try:
            order_id = payment_entity.get("order_id")
            payment_id = payment_entity.get("id")
            amount = payment_entity.get("amount", 0) / 100  # Convert from paise
            
            # Update payment record
            result = await db.execute(
                select(PaymentTransaction).where(
                    PaymentTransaction.order_id == order_id
                )
            )
            payment_record = result.scalar_one_or_none()
            
            if payment_record:
                payment_record.status = "completed"
                payment_record.payment_id = payment_id
                payment_record.updated_at = datetime.utcnow()
                # Store event_id to prevent duplicate processing
                if payment_record.notes:
                    payment_record.notes += f', "event_id": "{event_id}"'
                else:
                    payment_record.notes = f'{{"event_id": "{event_id}"}}'
                    
                await db.commit()
                logger.info("Payment captured", 
                    tracking_id=payment_record.tracking_id,
                    payment_id=payment_id,
                    amount=amount)
            else:
                logger.warning("Payment record not found for captured payment", order_id=order_id)
                
        except Exception as e:
            logger.error("Error handling payment captured", error=str(e))
            await db.rollback()
    
    async def _handle_payment_failed(self, payment_entity: Dict, event_id: str, db: AsyncSession):
        """Handle failed payment."""
        try:
            order_id = payment_entity.get("order_id")
            payment_id = payment_entity.get("id")
            error_description = payment_entity.get("error_description", "Unknown error")
            
            result = await db.execute(
                select(PaymentTransaction).where(
                    PaymentTransaction.order_id == order_id
                )
            )
            payment_record = result.scalar_one_or_none()
            
            if payment_record:
                payment_record.status = "failed"
                payment_record.payment_id = payment_id
                payment_record.error_message = error_description
                payment_record.updated_at = datetime.utcnow()
                # Store event_id
                if payment_record.notes:
                    payment_record.notes += f', "event_id": "{event_id}"'
                else:
                    payment_record.notes = f'{{"event_id": "{event_id}"}}'
                    
                await db.commit()
                logger.info("Payment failed", 
                    tracking_id=payment_record.tracking_id,
                    error=error_description)
            
        except Exception as e:
            logger.error("Error handling payment failed", error=str(e))
            await db.rollback()
    
    async def _handle_payment_authorized(self, payment_entity: Dict, event_id: str, db: AsyncSession):
        """Handle payment authorization (for two-step payments)."""
        try:
            order_id = payment_entity.get("order_id")
            payment_id = payment_entity.get("id")
            
            result = await db.execute(
                select(PaymentTransaction).where(
                    PaymentTransaction.order_id == order_id
                )
            )
            payment_record = result.scalar_one_or_none()
            
            if payment_record:
                payment_record.status = "authorized"
                payment_record.payment_id = payment_id
                payment_record.updated_at = datetime.utcnow()
                await db.commit()
                logger.info("Payment authorized", tracking_id=payment_record.tracking_id)
                
        except Exception as e:
            logger.error("Error handling payment authorized", error=str(e))
            await db.rollback()
    
    async def _handle_order_paid(self, order_entity: Dict, event_id: str, db: AsyncSession):
        """Handle order paid event."""
        try:
            order_id = order_entity.get("id")
            amount = order_entity.get("amount_paid", 0) / 100
            
            result = await db.execute(
                select(PaymentTransaction).where(
                    PaymentTransaction.order_id == order_id
                )
            )
            payment_record = result.scalar_one_or_none()
            
            if payment_record:
                payment_record.status = "paid"
                payment_record.updated_at = datetime.utcnow()
                await db.commit()
                logger.info("Order paid", tracking_id=payment_record.tracking_id, amount=amount)
                
        except Exception as e:
            logger.error("Error handling order paid", error=str(e))
            await db.rollback()
    
    async def _handle_refund_created(self, refund_entity: Dict, event_id: str, db: AsyncSession):
        """Handle refund created event."""
        try:
            payment_id = refund_entity.get("payment_id")
            refund_id = refund_entity.get("id")
            amount = refund_entity.get("amount", 0) / 100
            
            logger.info("Refund created", 
                payment_id=payment_id, 
                refund_id=refund_id,
                amount=amount)
            # Additional refund handling logic can be added here
            
        except Exception as e:
            logger.error("Error handling refund created", error=str(e))
    
    async def _handle_refund_processed(self, refund_entity: Dict, event_id: str, db: AsyncSession):
        """Handle refund processed event."""
        try:
            payment_id = refund_entity.get("payment_id")
            refund_id = refund_entity.get("id")
            amount = refund_entity.get("amount", 0) / 100
            
            logger.info("Refund processed", 
                payment_id=payment_id,
                refund_id=refund_id, 
                amount=amount)
            # Additional refund completion logic can be added here
            
        except Exception as e:
            logger.error("Error handling refund processed", error=str(e))

    async def create_razorpay_order(self, amount: float, notes: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create Razorpay order for in-app payment."""
        try:
            logger.info("Creating Razorpay order for in-app payment", amount=amount)
            
            # Generate unique receipt ID
            receipt_id = f"RCPT_{uuid.uuid4().hex[:12].upper()}"
            
            # Create order data
            order_data = {
                "amount": int(amount * 100),  # Convert to paise
                "currency": "INR",
                "receipt": receipt_id,
                "notes": notes or {
                    "payment_type": "in_app_payment",
                    "created_via": "flutter_chat_app"
                }
            }
            
            # Create Razorpay order
            order = self.razorpay_client.order.create(order_data)
            logger.info("Razorpay order created", order_id=order['id'])
            
            return {
                "success": True,
                "order_id": order['id'],
                "amount": amount,
                "currency": order['currency'],
                "status": order['status'],
                "receipt": receipt_id,
                "key_id": settings.RAZORPAY_KEY_ID  # Send key_id to frontend
            }
            
        except Exception as e:
            logger.error("Failed to create Razorpay order", error=str(e))
            return {
                "success": False,
                "error": str(e)
            }

    async def verify_payment_status(self, payment_id: str, order_id: str) -> Dict[str, Any]:
        """
        Verify payment status using Razorpay APIs.
        
        Args:
            payment_id: Razorpay payment ID
            order_id: Razorpay order ID
            
        Returns:
            Dict with verification results including payment status and settlement info
        """
        try:
            logger.info("Verifying payment status", payment_id=payment_id, order_id=order_id)
            
            # Fetch payment details from Razorpay
            payment_details = self.razorpay_client.payment.fetch(payment_id)
            order_details = self.razorpay_client.order.fetch(order_id)
            
            payment_status = payment_details.get('status', 'unknown')
            payment_method = payment_details.get('method', 'unknown')
            amount = payment_details.get('amount', 0) / 100  # Convert from paise
            
            logger.info("Payment verification details", 
                payment_id=payment_id,
                status=payment_status,
                method=payment_method,
                amount=amount)
            
            # Check if payment is captured (settled)
            is_captured = payment_status == 'captured'
            is_successful = payment_status in ['captured', 'authorized']
            
            return {
                "success": True,
                "payment_id": payment_id,
                "order_id": order_id,
                "status": payment_status,
                "method": payment_method,
                "amount": amount,
                "currency": payment_details.get('currency', 'INR'),
                "is_captured": is_captured,
                "is_successful": is_successful,
                "captured_at": payment_details.get('captured_at'),
                "created_at": payment_details.get('created_at'),
                "order_notes": order_details.get('notes', {}),
                "payment_details": {
                    "bank": payment_details.get('bank', ''),
                    "wallet": payment_details.get('wallet', ''),
                    "vpa": payment_details.get('vpa', ''),
                    "acquirer_data": payment_details.get('acquirer_data', {})
                }
            }
            
        except Exception as e:
            logger.error("Payment verification failed", 
                payment_id=payment_id, 
                order_id=order_id, 
                error=str(e))
            return {
                "success": False,
                "error": f"Payment verification failed: {str(e)}"
            }