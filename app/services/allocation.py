from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import datetime

from app.models.wallet import Wallet
from app.models.ledger import LedgerTransaction, TransactionType
from app.models.purchase import Purchase, PurchaseStatus
from app.models.subscription import Subscription
from app.services.catalog import get_subscription_plan, get_credit_pack
from sqlalchemy.sql import func


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


def initialize_purchase(
    db: Session,
    user_id: int,
    product_id: str,
    payment_provider: str,
    payment_reference: str
) -> Purchase:
    """Creates a PENDING purchase from the catalog snapshot."""
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
                payment_reference=payment_reference,
                status=PurchaseStatus.PENDING
            )
            db.add(purchase)
            db.flush()
        return purchase
    except IntegrityError:
        raise AllocationIdempotencyError(f"Purchase {payment_provider}:{payment_reference} already initialized.")


def fulfill_purchase(
    db: Session,
    purchase_id: int,
    verified_amount: int = None,
    verified_currency: str = None,
    provider_transaction_id: str = None,
) -> Purchase:
    """Fulfills a PENDING purchase, verifying the amount/currency if supplied, and allocates credits."""
    try:
        with db.begin_nested():
            purchase = db.query(Purchase).filter(Purchase.id == purchase_id).with_for_update().first()
            if not purchase:
                raise AllocationError("Purchase not found.")

            if purchase.status == PurchaseStatus.SUCCESS:
                raise AllocationIdempotencyError("Purchase already fulfilled.")

            if purchase.status != PurchaseStatus.PENDING:
                raise AllocationError(f"Cannot fulfill purchase in state: {purchase.status.name}")

            if verified_amount is not None and verified_amount != purchase.price_amount:
                raise AllocationError(f"Amount mismatch. Expected {purchase.price_amount}, got {verified_amount}.")

            if verified_currency is not None and verified_currency != purchase.price_currency:
                raise AllocationError(f"Currency mismatch. Expected {purchase.price_currency}, got {verified_currency}.")

            wallet = db.query(Wallet).filter(Wallet.user_id == purchase.user_id).with_for_update().first()
            if not wallet:
                raise AllocationError("User wallet not found.")

            wallet.purchased_balance += purchase.credit_allocation

            tx = LedgerTransaction(
                wallet_id=wallet.id,
                amount=purchase.credit_allocation,
                transaction_type=TransactionType.PURCHASE,
                reference_id=f"purchase_{purchase.id}"
            )
            db.add(tx)

            purchase.status = PurchaseStatus.SUCCESS
            purchase.paid_at = func.now()
            if provider_transaction_id:
                purchase.provider_transaction_id = provider_transaction_id

            db.flush()
        return purchase
    except IntegrityError:
        raise AllocationIdempotencyError("Purchase already fulfilled via ledger constraint.")
