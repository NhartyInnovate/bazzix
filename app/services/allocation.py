from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import datetime
import logging

from app.models.wallet import Wallet
from app.models.ledger import LedgerTransaction, TransactionType
from app.models.purchase import Purchase, PurchaseStatus
from app.models.subscription import Subscription
from app.services.catalog import get_subscription_plan, get_credit_pack
from sqlalchemy.sql import func

logger = logging.getLogger(__name__)


class AllocationIdempotencyError(Exception):
    pass

class AllocationError(Exception):
    pass

class AllocationValidationError(AllocationError):
    """Raised for non-retryable payment data mismatches (amount, currency)."""
    pass

class AllocationTransientError(AllocationError):
    """Raised for recoverable fulfillment or resource lookup failures."""
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
    paid_at: datetime.datetime = None,
    allow_recovery: bool = False,
) -> Purchase:
    """Fulfills a PENDING purchase (or FAILED if allow_recovery=True), verifying the amount/currency if supplied, and allocates credits."""
    with db.begin_nested():
        purchase = db.query(Purchase).filter(Purchase.id == purchase_id).with_for_update().first()
        if not purchase:
            raise AllocationTransientError("Purchase not found.")

        if purchase.status == PurchaseStatus.SUCCESS:
            raise AllocationIdempotencyError("Purchase already fulfilled.")

        if verified_amount is not None and verified_amount != purchase.price_amount:
            raise AllocationValidationError(f"Amount mismatch. Expected {purchase.price_amount}, got {verified_amount}.")

        if verified_currency is not None and verified_currency != purchase.price_currency:
            raise AllocationValidationError(f"Currency mismatch. Expected {purchase.price_currency}, got {verified_currency}.")

        if purchase.status != PurchaseStatus.PENDING:
            if allow_recovery and purchase.status == PurchaseStatus.FAILED:
                logger.warning(
                    f"Recovering purchase {purchase.id} (ref={purchase.payment_reference}) "
                    f"from FAILED to SUCCESS via verified payment."
                )
            else:
                raise AllocationValidationError(f"Cannot fulfill purchase in state: {purchase.status.name}")

        wallet = db.query(Wallet).filter(Wallet.user_id == purchase.user_id).with_for_update().first()
        if not wallet:
            try:
                with db.begin_nested():
                    wallet = Wallet(
                        user_id=purchase.user_id,
                        subscription_balance=0,
                        purchased_balance=0,
                        reserved_balance=0
                    )
                    db.add(wallet)
                    db.flush()
            except IntegrityError:
                # Concurrency race: another transaction provisioned the wallet simultaneously.
                # Re-fetch the newly created wallet with lock.
                wallet = db.query(Wallet).filter(Wallet.user_id == purchase.user_id).with_for_update().first()
                if not wallet:
                    raise AllocationTransientError("Failed to acquire wallet after concurrent creation.")

        wallet.purchased_balance += purchase.credit_allocation

        tx = LedgerTransaction(
            wallet_id=wallet.id,
            amount=purchase.credit_allocation,
            transaction_type=TransactionType.PURCHASE,
            reference_id=f"purchase_{purchase.id}"
        )
        db.add(tx)

        purchase.status = PurchaseStatus.SUCCESS
        purchase.paid_at = paid_at if paid_at is not None else func.now()
        if provider_transaction_id:
            purchase.provider_transaction_id = provider_transaction_id

        try:
            db.flush()
        except IntegrityError as e:
            # Check if ledger unique constraint caused this (another process already fulfilled this purchase)
            existing_tx = db.query(LedgerTransaction).filter(
                LedgerTransaction.transaction_type == TransactionType.PURCHASE,
                LedgerTransaction.reference_id == f"purchase_{purchase.id}"
            ).first()
            if existing_tx:
                raise AllocationIdempotencyError("Purchase already fulfilled via ledger constraint.") from e
            raise

    return purchase
