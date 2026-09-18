from datetime import datetime
from sqlalchemy.orm import Session
from app.models.ai_request import AIRequestLog, RequestStatus
from app.models.ledger import LedgerTransaction, TransactionType
from app.models.wallet import Wallet

def reconcile_stale_requests(db: Session, cutoff_time: datetime) -> dict:
    summary = {
        "inspected_count": 0,
        "reconciled_count": 0,
        "released_count": 0,
        "already_settled_count": 0,
        "overrun_count": 0,
        "skipped_count": 0,
        "failed_count": 0
    }
    
    # 1. Find stale pending requests
    stale_requests = db.query(AIRequestLog).filter(
        AIRequestLog.status == RequestStatus.PENDING,
        AIRequestLog.updated_at < cutoff_time
    ).all()
    
    summary["inspected_count"] = len(stale_requests)
    
    for ai_request in stale_requests:
        try:
            # Check ledger
            ledger_events = db.query(LedgerTransaction).filter(
                LedgerTransaction.reference_id == str(ai_request.id)
            ).all()
            
            types = {tx.transaction_type: tx for tx in ledger_events}
            
            # State A: PENDING + no reservation
            if TransactionType.RESERVATION not in types:
                ai_request.status = RequestStatus.FAILED
                db.add(ai_request)
                db.commit()
                summary["reconciled_count"] += 1
                continue
                
            # State D: PENDING + RESERVATION_RELEASE
            if TransactionType.RESERVATION_RELEASE in types:
                if TransactionType.CHARGE in types:
                    ai_request.status = RequestStatus.COMPLETED
                else:
                    ai_request.status = RequestStatus.FAILED
                db.add(ai_request)
                db.commit()
                summary["already_settled_count"] += 1
                summary["reconciled_count"] += 1
                continue
                
            # State C: Overrun (RESERVATION exists, but also usage exists)
            if ai_request.prompt_tokens is not None:
                summary["overrun_count"] += 1
                continue
                
            # State B: Crash (RESERVATION + no usage)
            # Acquire wallet lock to safely release
            wallet = db.query(Wallet).filter(Wallet.user_id == ai_request.user_id).with_for_update().first()
            if not wallet:
                db.rollback()
                summary["failed_count"] += 1
                continue
                
            # Verify no release was added while waiting for lock
            release_check = db.query(LedgerTransaction).filter(
                LedgerTransaction.reference_id == str(ai_request.id),
                LedgerTransaction.transaction_type == TransactionType.RESERVATION_RELEASE
            ).first()
            
            if release_check:
                db.rollback()
                # Should not happen as we checked above, but safe fallback
                summary["failed_count"] += 1
                continue
                
            reservation_tx = types[TransactionType.RESERVATION]
            reserved_amount = abs(reservation_tx.amount)
            
            # Release reservation
            wallet.reserved_balance -= reserved_amount
            if wallet.reserved_balance < 0:
                wallet.reserved_balance = 0
                
            db.add(LedgerTransaction(
                wallet_id=wallet.id,
                amount=reserved_amount,
                transaction_type=TransactionType.RESERVATION_RELEASE,
                reference_id=str(ai_request.id)
            ))
            
            ai_request.status = RequestStatus.FAILED
            db.add(ai_request)
            db.commit()
            
            summary["released_count"] += 1
            summary["reconciled_count"] += 1

        except Exception as e:
            db.rollback()
            print(f"Reconciliation error on request {ai_request.id}: {e}")
            summary["failed_count"] += 1
            
    return summary