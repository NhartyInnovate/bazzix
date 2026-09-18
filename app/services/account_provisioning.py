import datetime
from sqlalchemy.orm import Session
from app.models.wallet import Wallet
from app.models.subscription import Subscription, SubscriptionStatus
from app.services.allocation import allocate_subscription_credits, AllocationIdempotencyError

def provision_new_user_account(db: Session, user_id: int) -> None:
    """
    Provisions a Wallet and Free Subscription for a new user atomically.
    Expects to be called within an active transaction.
    """
    # 1. Create Wallet if it doesn't exist
    wallet = db.query(Wallet).filter(Wallet.user_id == user_id).with_for_update().first()
    if not wallet:
        wallet = Wallet(user_id=user_id, subscription_balance=0, purchased_balance=0, reserved_balance=0)
        db.add(wallet)
        db.flush()

    # 2. Create Free Subscription if no active subscription exists
    active_sub = db.query(Subscription).filter(
        Subscription.user_id == user_id,
        Subscription.status == SubscriptionStatus.ACTIVE
    ).first()
    
    if not active_sub:
        now = datetime.datetime.now(datetime.timezone.utc)
        end_period = now + datetime.timedelta(days=30)
        
        active_sub = Subscription(
            user_id=user_id,
            plan_id="free",
            status=SubscriptionStatus.ACTIVE,
            current_period_start=now,
            current_period_end=end_period
        )
        db.add(active_sub)
        db.flush()

    # 3. Allocate free credits
    try:
        period_start = active_sub.current_period_start
        if period_start.tzinfo is None:
            period_start = period_start.replace(tzinfo=datetime.timezone.utc)
        
        allocate_subscription_credits(
            db=db,
            subscription_id=active_sub.id,
            user_id=user_id,
            plan_id=active_sub.plan_id,
            period_start=period_start
        )
    except AllocationIdempotencyError:
        pass
