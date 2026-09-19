from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from app.db.dependencies import get_db

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


@router.get("/me")
def me(current_user=Depends(get_current_user)):
    return {
        "id": current_user.id,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "email": current_user.email,
    }

@router.get("/me/wallet")
def get_wallet(current_user=Depends(get_current_user), db=Depends(get_db)):
    from app.models.wallet import Wallet
    from app.schemas.user import WalletResponse
    wallet = db.query(Wallet).filter(Wallet.user_id == current_user.id).first()
    if not wallet:
        return WalletResponse(
            subscription_balance=0,
            purchased_balance=0,
            reserved_balance=0,
            available_credits=0
        )
    return WalletResponse(
        subscription_balance=wallet.subscription_balance,
        purchased_balance=wallet.purchased_balance,
        reserved_balance=wallet.reserved_balance,
        available_credits=wallet.available_credits
    )