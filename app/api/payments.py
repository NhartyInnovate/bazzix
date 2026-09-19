import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.core.dependencies import get_current_user
from app.models.user import User

from app.schemas.payment import CheckoutRequest, CheckoutResponse, PurchaseStatusResponse
from app.services.catalog import get_credit_pack
from app.services.allocation import initialize_purchase
from app.services.paystack import PaystackProvider
from app.services.payment import PaymentInitializationError

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/payments",
    tags=["Payments"],
)

@router.post("/checkout", response_model=CheckoutResponse)
def checkout(
    request: CheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 1. Server Authority Lookup
    pack = get_credit_pack(request.product_id)
    if not pack or not pack.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or inactive product."
        )

    # 2. Payment Reference Generation
    # UUID4 is alphanumeric with hyphens, safe for Paystack: "bazzix_<uuid>"
    payment_reference = f"bazzix_{uuid.uuid4()}"

    # 3. Initialize Purchase (PENDING snapshot)
    try:
        purchase = initialize_purchase(
            db=db,
            user_id=current_user.id,
            product_id=pack.id,
            payment_provider="paystack",
            payment_reference=payment_reference
        )
    except Exception as e:
        logger.error(f"Failed to initialize purchase: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not initialize purchase."
        )

    # 4. Initialize Paystack Transaction
    provider = PaystackProvider()
    
    try:
        result = provider.initialize_transaction(
            amount=purchase.price_amount,
            currency=purchase.price_currency,
            email=current_user.email,
            reference=purchase.payment_reference
        )
    except PaymentInitializationError as e:
        logger.error(f"Payment provider initialization failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to communicate with payment provider."
        )
    except Exception as e:
        logger.error(f"Unexpected error during payment initialization: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during checkout."
        )

    return CheckoutResponse(
        authorization_url=result.authorization_url,
        reference=result.provider_reference,
        provider="paystack"
    )

@router.get("/{reference}", response_model=PurchaseStatusResponse)
def get_purchase_status(
    reference: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from app.models.purchase import Purchase
    from app.schemas.payment import PurchaseStatusResponse
    purchase = db.query(Purchase).filter(
        Purchase.payment_reference == reference
    ).first()
    
    if not purchase or purchase.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase not found."
        )
        
    return PurchaseStatusResponse(
        reference=purchase.payment_reference,
        status=purchase.status.name
    )
