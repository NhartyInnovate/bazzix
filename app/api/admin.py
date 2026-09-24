from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case, or_, text
from app.db.dependencies import get_db
from app.core.dependencies import get_current_admin
from app.models.user import User, RoleType
from app.models.wallet import Wallet
from app.models.ledger import LedgerTransaction, TransactionType
from app.models.ai_request import AIRequestLog, RequestStatus
from app.models.purchase import Purchase, PurchaseStatus
from app.models.audit import AdminAuditLog
from app.models.conversation import Conversation
from app.schemas.admin import (
    AdminStatsResponse, AdminUserListResponse, AdminUserSummary, AdminUserDetail,
    AIUsageItem, AIUsageListResponse,
    PurchaseItem, PurchaseListResponse,
    LedgerItem, LedgerListResponse,
    CreditAdjustmentRequest, CreditAdjustmentResponse,
    AuditLogItem, AuditLogListResponse,
    AdminHealthResponse
)
from app.services.credit_manager import adjust_credits, InsufficientCreditsError
from app.core.config import settings

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(get_current_admin)]
)

@router.get("/stats", response_model=AdminStatsResponse)
def get_admin_stats(db: Session = Depends(get_db)):
    total_users = db.query(func.count(User.id)).scalar() or 0
    active_users = db.query(func.count(User.id)).filter(User.is_active == True).scalar() or 0

    total_ai = db.query(func.count(AIRequestLog.id)).scalar() or 0
    succ_ai = db.query(func.count(AIRequestLog.id)).filter(AIRequestLog.status == RequestStatus.COMPLETED).scalar() or 0
    fail_ai = db.query(func.count(AIRequestLog.id)).filter(AIRequestLog.status == RequestStatus.FAILED).scalar() or 0

    total_cost = db.query(func.sum(AIRequestLog.provider_cost)).scalar() or 0.0

    consumed_credits = db.query(func.sum(LedgerTransaction.amount)).filter(
        LedgerTransaction.transaction_type == TransactionType.CHARGE
    ).scalar() or 0

    succ_purchases = db.query(func.count(Purchase.id)).filter(Purchase.status == PurchaseStatus.SUCCESS).scalar() or 0
    total_rev = db.query(func.sum(Purchase.price_amount)).filter(Purchase.status == PurchaseStatus.SUCCESS).scalar() or 0.0

    return AdminStatsResponse(
        total_users=total_users,
        active_users=active_users,
        total_ai_requests=total_ai,
        successful_ai_requests=succ_ai,
        failed_ai_requests=fail_ai,
        total_provider_cost=float(total_cost),
        total_credits_consumed=abs(int(consumed_credits)),
        total_successful_purchases=succ_purchases,
        total_purchase_revenue=float(total_rev)
    )

@router.get("/users", response_model=AdminUserListResponse)
def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str = Query(None),
    is_active: bool = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(User, Wallet).outerjoin(Wallet, User.id == Wallet.user_id)

    if search:
        query = query.filter(or_(
            User.email.ilike(f"%{search}%"),
            User.first_name.ilike(f"%{search}%"),
            User.last_name.ilike(f"%{search}%")
        ))

    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    total = query.count()
    users_with_wallets = query.order_by(User.id.desc()).offset((page - 1) * size).limit(size).all()

    result = []
    for user, wallet in users_with_wallets:
        result.append(AdminUserSummary(
            id=user.id,
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            role=user.role.name,
            is_active=user.is_active,
            is_verified=user.is_verified,
            created_at=user.created_at,
            available_credits=wallet.available_credits if wallet else 0
        ))

    return AdminUserListResponse(
        users=result,
        total=total,
        page=page,
        size=size
    )

@router.get("/users/{user_id}", response_model=AdminUserDetail)
def get_user_detail(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    wallet = db.query(Wallet).filter(Wallet.user_id == user_id).first()
    conv_count = db.query(func.count(Conversation.id)).filter(Conversation.user_id == user_id).scalar() or 0

    return AdminUserDetail(
        id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        role=user.role.name,
        is_active=user.is_active,
        is_verified=user.is_verified,
        created_at=user.created_at,
        available_credits=wallet.available_credits if wallet else 0,
        subscription_balance=wallet.subscription_balance if wallet else 0,
        purchased_balance=wallet.purchased_balance if wallet else 0,
        reserved_balance=wallet.reserved_balance if wallet else 0,
        conversations_count=conv_count
    )

@router.get("/users/{user_id}/usage", response_model=AIUsageListResponse)
def get_user_usage(
    user_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    query = db.query(AIRequestLog).filter(AIRequestLog.user_id == user_id)
    total = query.count()
    logs = query.order_by(AIRequestLog.id.desc()).offset((page-1)*size).limit(size).all()

    items = []
    for log in logs:
        # Determine credits charged by looking up CHARGE transaction for this request
        charge_tx = db.query(LedgerTransaction).filter(
            LedgerTransaction.reference_id == str(log.id),
            LedgerTransaction.transaction_type == TransactionType.CHARGE
        ).first()
        credits_charged = abs(charge_tx.amount) if charge_tx else 0

        req_tok = log.prompt_tokens or 0
        res_tok = log.completion_tokens or 0
        tot_tok = req_tok + res_tok

        items.append(AIUsageItem(
            id=log.id,
            model=log.model,
            request_tokens=log.prompt_tokens,
            response_tokens=log.completion_tokens,
            total_tokens=tot_tok,
            provider_cost=float(log.provider_cost) if log.provider_cost else None,
            credits_charged=credits_charged,
            status=log.status.name,
            created_at=log.created_at
        ))

    return AIUsageListResponse(items=items, total=total, page=page, size=size)

@router.get("/users/{user_id}/purchases", response_model=PurchaseListResponse)
def get_user_purchases(
    user_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    query = db.query(Purchase).filter(Purchase.user_id == user_id)
    total = query.count()
    purchases = query.order_by(Purchase.id.desc()).offset((page-1)*size).limit(size).all()

    items = [PurchaseItem(
        id=p.id,
        product_id=p.product_id,
        price_amount=p.price_amount,
        price_currency=p.price_currency,
        credit_allocation=p.credit_allocation,
        payment_reference=p.payment_reference,
        status=p.status.name,
        created_at=p.created_at
    ) for p in purchases]

    return PurchaseListResponse(items=items, total=total, page=page, size=size)

@router.get("/users/{user_id}/ledger", response_model=LedgerListResponse)
def get_user_ledger(
    user_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    wallet = db.query(Wallet).filter(Wallet.user_id == user_id).first()
    if not wallet:
        return LedgerListResponse(items=[], total=0, page=page, size=size)

    query = db.query(LedgerTransaction).filter(LedgerTransaction.wallet_id == wallet.id)
    total = query.count()
    txs = query.order_by(LedgerTransaction.id.desc()).offset((page-1)*size).limit(size).all()

    items = [LedgerItem(
        id=t.id,
        amount=t.amount,
        transaction_type=t.transaction_type.name,
        reference_id=t.reference_id,
        created_at=t.created_at
    ) for t in txs]

    return LedgerListResponse(items=items, total=total, page=page, size=size)

@router.post("/users/{user_id}/credits/adjust", response_model=CreditAdjustmentResponse)
def admin_adjust_user_credits(
    user_id: int,
    req: CreditAdjustmentRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_current_admin)
):
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")

    try:
        tx = adjust_credits(
            db=db,
            user_id=user_id,
            amount=req.amount,
            reference_id=req.reason[:255]
        )
    except InsufficientCreditsError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    audit = AdminAuditLog(
        admin_user_id=admin_user.id,
        target_user_id=target_user.id,
        target_user_email=target_user.email,
        action="CREDIT_ADJUSTMENT",
        details={"amount": req.amount, "reason": req.reason}
    )
    db.add(audit)

    db.commit()
    db.refresh(tx)

    wallet = db.query(Wallet).filter(Wallet.id == tx.wallet_id).first()

    return CreditAdjustmentResponse(
        status="success",
        transaction_id=tx.id,
        new_balance=wallet.available_credits
    )

@router.get("/audit-logs", response_model=AuditLogListResponse)
def get_audit_logs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    action: str = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(AdminAuditLog)
    if action:
        query = query.filter(AdminAuditLog.action == action)

    total = query.count()
    logs = query.order_by(AdminAuditLog.id.desc()).offset((page-1)*size).limit(size).all()

    items = [AuditLogItem(
        id=L.id,
        admin_user_id=L.admin_user_id,
        target_user_id=L.target_user_id,
        target_user_email=L.target_user_email,
        action=L.action,
        details=L.details,
        created_at=L.created_at
    ) for L in logs]

    return AuditLogListResponse(items=items, total=total, page=page, size=size)

@router.get("/health", response_model=AdminHealthResponse)
def admin_health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"

    return AdminHealthResponse(
        status="healthy" if db_status == "ok" else "degraded",
        database=db_status,
        openai_configured=bool(settings.OPENAI_API_KEY),
        paystack_configured=bool(settings.PAYSTACK_SECRET_KEY) if hasattr(settings, "PAYSTACK_SECRET_KEY") else False,
        resend_configured=bool(settings.RESEND_API_KEY) if hasattr(settings, "RESEND_API_KEY") else False
    )
