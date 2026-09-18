from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import datetime

from app.models.wallet import Wallet
from app.models.ledger import LedgerTransaction, TransactionType
from app.models.purchase import Purchase
from app.models.subscription import Subscription
from app.services.catalog import get_subscription_plan, get_credit_pack


class AllocationIdempotencyError(Exception):
    pass

class AllocationError(Exception):
    pass


def allocate_subscription_credits(
    db: Session,
    subscription_id: int,
    user_id: int,
    plan_id: str,
    period_start: datetime.datetime
) -> LedgerTransaction:
    plan = get_subscription_plan(plan_id)
    if not plan:
        raise AllocationError(f"Unknown subscription plan: {plan_id}")

    ref_id = f"sub_alloc_{subscription_id}_{int(period_start.timestamp())}"
    amount = plan.credits_per_month
    if amount <= 0:
        raise AllocationError("Subscription plan has zero or negative credits.")
    
    try:
        with db.begin_nested():
            wallet = db.query(Wallet).filter(Wallet.user_id == user_id).with_for_update().first()
            if not wallet:
                raise AllocationError("User wallet not found.")
            
            wallet.subscription_balance += amount
            
            tx = LedgerTransaction(
                wallet_id=wallet.id,
                amount=amount,
                transaction_type=TransactionType.SUBSCRIPTION_ALLOCATION,
                reference_id=ref_id
            )
            db.add(tx)
            db.flush()
        return tx
    except IntegrityError:
        raise AllocationIdempotencyError(f"Subscription allocation {ref_id} already processed.")


def allocate_purchase_credits(
    db: Session,
    user_id: int,
    product_id: str,
    payment_provider: str,
    payment_reference: str
) -> Purchase:
    pack = get_credit_pack(product_id)
    if not pack:
        raise AllocationError(f"Unknown credit pack: {product_id}")
    
    amount = pack.credit_amount
    if amount <= 0:
        raise AllocationError("Credit pack has zero or negative credits.")
    
    try:
        with db.begin_nested():
            purchase = Purchase(
                user_id=user_id,
                product_id=pack.id,
                product_name_snapshot=pack.name,
                price_amount=pack.price_ngn,
                price_currency="NGN",
                credit_allocation=amount,
                payment_provider=payment_provider,
                payment_reference=payment_reference
            )
            db.add(purchase)
            db.flush()
            
            wallet = db.query(Wallet).filter(Wallet.user_id == user_id).with_for_update().first()
            if not wallet:
                raise AllocationError("User wallet not found.")
            
            wallet.purchased_balance += amount
            
            tx = LedgerTransaction(
                wallet_id=wallet.id,
                amount=amount,
                transaction_type=TransactionType.PURCHASE,
                reference_id=f"purchase_{purchase.id}"
            )
            db.add(tx)
            db.flush()
        return purchase
    except IntegrityError:
        raise AllocationIdempotencyError(f"Purchase {payment_provider}:{payment_reference} already processed.")
