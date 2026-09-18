from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.wallet import Wallet
from app.models.ledger import LedgerTransaction, TransactionType

class InsufficientCreditsError(Exception):
    pass

class DuplicateReservationError(Exception):
    pass

def reserve_credits(db: Session, user_id: int, request_id: int, max_cost: int) -> int:
    """
    Reserves credits for an AI request using row-level locking.
    Returns the reserved amount.
    """
    if max_cost < 0:
        raise ValueError("max_cost cannot be negative")

    # Lock wallet to ensure concurrency safety
    wallet = db.query(Wallet).filter(Wallet.user_id == user_id).with_for_update().first()
    if not wallet:
        raise ValueError("Wallet not found")
        
    if wallet.available_credits < max_cost:
        raise InsufficientCreditsError(f"Insufficient available credits. Required: {max_cost}, Available: {wallet.available_credits}")
        
    # Idempotency check: Ensure this request hasn't already made a reservation.
    # We do this after acquiring the row lock, so concurrent duplicate requests 
    # will wait, and the second one will fail this check.
    existing_reservation = db.query(LedgerTransaction).filter(
        LedgerTransaction.reference_id == str(request_id),
        LedgerTransaction.transaction_type == TransactionType.RESERVATION
    ).first()
    if existing_reservation:
        raise DuplicateReservationError("Reservation already exists for this request")

    wallet.reserved_balance += max_cost
    
    # Immutable ledger event
    tx = LedgerTransaction(
        wallet_id=wallet.id,
        amount=-max_cost,
        transaction_type=TransactionType.RESERVATION,
        reference_id=str(request_id)
    )
    db.add(tx)
    
    # Commit immediately to release the row lock before provider execution
    db.commit()
    
    return max_cost

class DuplicateFinalizationError(Exception):
    pass

class MissingReservationError(Exception):
    pass

class SettlementInvariantError(Exception):
    pass

def finalize_and_settle_credits(
    db: Session,
    ai_request, # AIRequestLog
    status, # RequestStatus
    provider_request_id: str = None,
    prompt_tokens: int = None,
    completion_tokens: int = None,
    cached_tokens: int = None,
    usage_source = None # UsageSource
):
    from app.services.pricing import calculate_cost
    
    actual_bazzix_credits = 0
    actual_provider_cost = None
    
    # Calculate actual usage if we have the data
    if prompt_tokens is not None and completion_tokens is not None:
        cost_result = calculate_cost(
            provider=ai_request.provider,
            model=ai_request.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cached_tokens=cached_tokens or 0
        )
        actual_bazzix_credits = cost_result.bazzix_credits
        actual_provider_cost = cost_result.provider_cost

    wallet = db.query(Wallet).filter(Wallet.user_id == ai_request.user_id).with_for_update().first()
    if not wallet:
        raise ValueError("Wallet not found")
        
    # Check if there is an existing RESERVATION event for this request
    reservation_event = db.query(LedgerTransaction).filter(
        LedgerTransaction.reference_id == str(ai_request.id),
        LedgerTransaction.transaction_type == TransactionType.RESERVATION
    ).first()
    
    if not reservation_event:
        db.rollback()
        raise MissingReservationError("Cannot finalize: no existing reservation found for this request.")
        
    # Idempotency check: has it already been released/finalized?
    release_event = db.query(LedgerTransaction).filter(
        LedgerTransaction.reference_id == str(ai_request.id),
        LedgerTransaction.transaction_type == TransactionType.RESERVATION_RELEASE
    ).first()
    
    if release_event:
        db.rollback()
        raise DuplicateFinalizationError("This request has already been finalized/settled.")
        
    reserved_amount = abs(reservation_event.amount)
    
    # 1. Release Reservation
    wallet.reserved_balance -= reserved_amount
    if wallet.reserved_balance < 0:
        wallet.reserved_balance = 0
        
    db.add(LedgerTransaction(
        wallet_id=wallet.id,
        amount=reserved_amount,
        transaction_type=TransactionType.RESERVATION_RELEASE,
        reference_id=str(ai_request.id)
    ))
    
    # 2. Charge actual Bazzix Credits
    if actual_bazzix_credits > 0:
        # Prevent charging more than we have (after reservation release)
        if actual_bazzix_credits > wallet.available_credits:
            db.rollback()
            
            # Preserve usage info on AIRequestLog before throwing
            if provider_request_id:
                ai_request.provider_request_id = provider_request_id
            if prompt_tokens is not None:
                ai_request.prompt_tokens = prompt_tokens
            if cached_tokens is not None:
                ai_request.cached_tokens = cached_tokens
            if completion_tokens is not None:
                ai_request.completion_tokens = completion_tokens
            if actual_provider_cost is not None:
                ai_request.provider_cost = actual_provider_cost
            if usage_source is not None:
                ai_request.usage_source = usage_source
                
            # Do not change status so it stays PENDING/FAILED depending on what it was before
            db.add(ai_request)
            db.commit()
            raise SettlementInvariantError(f"Actual provider cost ({actual_bazzix_credits} credits) exceeds available balance ({wallet.available_credits}).")
            
        remaining_charge = actual_bazzix_credits
        
        # Consume subscription first
        if wallet.subscription_balance >= remaining_charge:
            wallet.subscription_balance -= remaining_charge
            remaining_charge = 0
        else:
            remaining_charge -= wallet.subscription_balance
            wallet.subscription_balance = 0
            
        # Consume purchased second
        if remaining_charge > 0:
            if wallet.purchased_balance >= remaining_charge:
                wallet.purchased_balance -= remaining_charge
                remaining_charge = 0
            else:
                wallet.purchased_balance = 0
                # wallet can't go negative, capped by available_credits check above
                
        db.add(LedgerTransaction(
            wallet_id=wallet.id,
            amount=-actual_bazzix_credits,
            transaction_type=TransactionType.CHARGE,
            reference_id=str(ai_request.id)
        ))
        
    # 3. Update AIRequestLog
    if provider_request_id:
        ai_request.provider_request_id = provider_request_id
    if prompt_tokens is not None:
        ai_request.prompt_tokens = prompt_tokens
    if cached_tokens is not None:
        ai_request.cached_tokens = cached_tokens
    if completion_tokens is not None:
        ai_request.completion_tokens = completion_tokens
    if actual_provider_cost is not None:
        ai_request.provider_cost = actual_provider_cost
    if usage_source is not None:
        ai_request.usage_source = usage_source
        
    ai_request.status = status
    db.add(ai_request)
    
    db.commit()
    return ai_request
