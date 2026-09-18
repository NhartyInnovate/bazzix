import hmac
import json
import logging
from datetime import datetime
from fastapi import APIRouter, Request, Header, HTTPException, status, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.dependencies import get_db
from app.models.purchase import Purchase
from app.services.allocation import fulfill_purchase, AllocationIdempotencyError, AllocationError

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/webhooks",
    tags=["Webhooks"],
)

@router.post("/paystack")
async def paystack_webhook(
    request: Request,
    x_paystack_signature: str = Header(None),
    db: Session = Depends(get_db)
):
    if not settings.PAYSTACK_SECRET_KEY:
        logger.error("PAYSTACK_SECRET_KEY is not configured.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    if not x_paystack_signature:
        logger.warning("Missing x-paystack-signature header in webhook payload.")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing signature")

    raw_body = await request.body()

    # Calculate HMAC SHA512
    computed_hmac = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode('utf-8'),
        raw_body,
        digestmod='sha512'
    ).hexdigest()

    if not hmac.compare_digest(computed_hmac, x_paystack_signature):
        logger.warning("Invalid x-paystack-signature header in webhook payload.")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        logger.error("Malformed JSON in Paystack webhook payload.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed JSON")

    event = payload.get("event")
    if event != "charge.success":
        logger.info(f"Ignoring unhandled Paystack event type: {event}")
        return {"status": "success"}

    data = payload.get("data", {})
    reference = data.get("reference")
    amount_kobo = data.get("amount")
    currency = data.get("currency")
    tx_id = data.get("id")
    paid_at_str = data.get("paid_at")

    if not reference or amount_kobo is None or not currency or not tx_id:
        logger.error("Missing required data fields in charge.success payload.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing required data fields")

    if not isinstance(amount_kobo, int) or amount_kobo <= 0:
        logger.error(f"Invalid amount in charge.success payload. reference={reference}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid amount")

    if amount_kobo % 100 != 0:
        logger.error(f"Fractional amount rejected in charge.success payload. reference={reference}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Amount must represent whole currency units")

    # The amount in Bazzix Purchase snapshot is the whole unit.
    amount_whole = amount_kobo // 100

    # Parse paid_at
    paid_at_dt = None
    if paid_at_str:
        try:
            # Example: 2023-01-01T12:00:00.000Z
            paid_at_dt = datetime.strptime(paid_at_str.replace("Z", "+0000"), "%Y-%m-%dT%H:%M:%S.%f%z")
        except ValueError:
            try:
                paid_at_dt = datetime.strptime(paid_at_str.replace("Z", "+0000"), "%Y-%m-%dT%H:%M:%S%z")
            except ValueError:
                pass  # Ignore unparseable date rather than crashing

    purchase = db.query(Purchase).filter(Purchase.payment_reference == reference).first()
    if not purchase:
        logger.info(f"Ignored Paystack webhook for unknown reference: {reference}")
        return {"status": "success"}

    try:
        fulfill_purchase(
            db=db,
            purchase_id=purchase.id,
            verified_amount=amount_whole,
            verified_currency=currency,
            provider_transaction_id=str(tx_id),
            paid_at=paid_at_dt
        )
        logger.info(f"Successfully fulfilled purchase via webhook. reference={reference}")
    except AllocationIdempotencyError:
        logger.info(f"Ignored duplicate Paystack webhook for already fulfilled purchase. reference={reference}")
    except AllocationError as e:
        logger.error(f"AllocationError fulfilling purchase via webhook. reference={reference}, error={str(e)}")
        # Do not throw 500, return 200 so Paystack stops retrying an invalid state (e.g., currency mismatch)
        # But we don't grant the credits.
    except Exception as e:
        logger.critical(f"Unexpected database failure fulfilling purchase via webhook. reference={reference}, error={str(e)}")
        # Return 500 so Paystack retries the payload
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database failure")

    return {"status": "success"}
