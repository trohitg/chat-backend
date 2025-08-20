"""Balance service for user wallet management."""

import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.dialects.postgresql import insert

from ..models.balance import (
    UserBalance, BalanceTransaction,
    BalanceResponse, TransactionHistoryResponse
)
import structlog

logger = structlog.get_logger()


class BalanceService:
    """Service class for handling user balance operations."""

    async def get_user_balance(self, user_id: str, db: AsyncSession) -> BalanceResponse:
        """Get current balance for a user."""
        try:
            logger.info("Getting user balance", user_id=user_id)
            
            # Get or create user balance
            result = await db.execute(
                select(UserBalance).where(UserBalance.user_id == user_id)
            )
            user_balance = result.scalar_one_or_none()
            
            if not user_balance:
                # Create new balance record with 0.0 balance
                user_balance = UserBalance(
                    user_id=user_id,
                    balance=0.0,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.add(user_balance)
                await db.commit()
                logger.info("Created new balance record", user_id=user_id)
            
            return BalanceResponse(
                user_id=user_balance.user_id,
                balance=user_balance.balance,
                last_updated=user_balance.updated_at
            )
            
        except Exception as e:
            logger.error("Error getting user balance", user_id=user_id, error=str(e))
            await db.rollback()
            raise

    async def get_transaction_history(
        self, 
        user_id: str, 
        db: AsyncSession,
        limit: int = 50,
        offset: int = 0
    ) -> List[TransactionHistoryResponse]:
        """Get transaction history for a user."""
        try:
            logger.info("Getting transaction history", user_id=user_id, limit=limit, offset=offset)
            
            result = await db.execute(
                select(BalanceTransaction)
                .where(BalanceTransaction.user_id == user_id)
                .order_by(desc(BalanceTransaction.created_at))
                .limit(limit)
                .offset(offset)
            )
            transactions = result.scalars().all()
            
            return [
                TransactionHistoryResponse(
                    id=tx.id,
                    transaction_type=tx.transaction_type,
                    amount=tx.amount,
                    description=tx.description,
                    reference_id=tx.reference_id,
                    reference_type=tx.reference_type,
                    created_at=tx.created_at
                )
                for tx in transactions
            ]
            
        except Exception as e:
            logger.error("Error getting transaction history", user_id=user_id, error=str(e))
            raise

    async def credit_balance(
        self,
        user_id: str,
        amount: float,
        description: str,
        reference_id: Optional[str] = None,
        reference_type: str = "payment",
        db: AsyncSession = None
    ) -> bool:
        """Credit amount to user balance (from successful payments)."""
        try:
            logger.info("Crediting balance", user_id=user_id, amount=amount, reference_id=reference_id)
            
            # Generate transaction ID
            transaction_id = f"tx_{uuid.uuid4().hex[:12]}"
            
            # Get or create user balance using UPSERT
            stmt = insert(UserBalance).values(
                user_id=user_id,
                balance=amount,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=['user_id'],
                set_=dict(
                    balance=UserBalance.balance + amount,
                    updated_at=datetime.utcnow()
                )
            )
            await db.execute(stmt)
            
            # Create transaction record
            transaction = BalanceTransaction(
                id=transaction_id,
                user_id=user_id,
                transaction_type="credit",
                amount=amount,
                description=description,
                reference_id=reference_id,
                reference_type=reference_type,
                created_at=datetime.utcnow()
            )
            db.add(transaction)
            
            await db.commit()
            logger.info("Balance credited successfully", user_id=user_id, amount=amount, transaction_id=transaction_id)
            return True
            
        except Exception as e:
            logger.error("Error crediting balance", user_id=user_id, amount=amount, error=str(e))
            await db.rollback()
            raise

    async def debit_balance(
        self,
        user_id: str,
        amount: float,
        description: str,
        reference_id: Optional[str] = None,
        reference_type: str = "usage",
        db: AsyncSession = None
    ) -> bool:
        """Debit amount from user balance (for usage/consumption)."""
        try:
            logger.info("Debiting balance", user_id=user_id, amount=amount, reference_id=reference_id)
            
            # Check current balance
            result = await db.execute(
                select(UserBalance).where(UserBalance.user_id == user_id)
            )
            user_balance = result.scalar_one_or_none()
            
            if not user_balance or user_balance.balance < amount:
                logger.warning("Insufficient balance", user_id=user_id, required=amount, available=user_balance.balance if user_balance else 0)
                return False
            
            # Generate transaction ID
            transaction_id = f"tx_{uuid.uuid4().hex[:12]}"
            
            # Update balance
            user_balance.balance -= amount
            user_balance.updated_at = datetime.utcnow()
            
            # Create transaction record
            transaction = BalanceTransaction(
                id=transaction_id,
                user_id=user_id,
                transaction_type="debit",
                amount=amount,
                description=description,
                reference_id=reference_id,
                reference_type=reference_type,
                created_at=datetime.utcnow()
            )
            db.add(transaction)
            
            await db.commit()
            logger.info("Balance debited successfully", user_id=user_id, amount=amount, transaction_id=transaction_id)
            return True
            
        except Exception as e:
            logger.error("Error debiting balance", user_id=user_id, amount=amount, error=str(e))
            await db.rollback()
            raise

    async def check_sufficient_balance(self, user_id: str, amount: float, db: AsyncSession) -> bool:
        """Check if user has sufficient balance for a transaction."""
        try:
            result = await db.execute(
                select(UserBalance.balance).where(UserBalance.user_id == user_id)
            )
            balance = result.scalar_one_or_none()
            return balance is not None and balance >= amount
            
        except Exception as e:
            logger.error("Error checking balance", user_id=user_id, error=str(e))
            return False