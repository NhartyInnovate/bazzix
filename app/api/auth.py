from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.schemas.auth import LoginRequest, ForgotPasswordRequest, ResetPasswordRequest
from app.core.auth import create_access_token, create_reset_token, verify_reset_token
from app.crud.user import authenticate_user, update_password
from app.crud.user import create_user, get_user_by_email
from app.db.dependencies import get_db
from app.schemas.user import UserCreate
from app.core.rate_limit import rate_limiter
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post("/register", dependencies=[Depends(rate_limiter(limit=5, window=60))])
def register(user: UserCreate, db: Session = Depends(get_db)):
    existing_user = get_user_by_email(db, user.email)

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered."
        )
    
    created_user = create_user(db, user)

    return {
        "message": "User registered successfully!",
        "user": {
            "id": created_user.id,
            "first_name": created_user.first_name,
            "last_name": created_user.last_name,
            "email": created_user.email,
        },
    }


@router.post("/login", dependencies=[Depends(rate_limiter(limit=5, window=60))])
def login(
    data: LoginRequest,
    db: Session = Depends(get_db),
):
    user = authenticate_user(
        db,
        data.email,
        data.password,
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )

    token = create_access_token(
        {"sub": str(user.id)}
    )

    return {
        "access_token": token,
        "token_type": "bearer",
    }


def send_reset_email(email: str, token: str):
    # In a real application, you would integrate SendGrid, Postmark, AWS SES, etc.
    reset_link = f"http://localhost:5173/reset-password?token={token}"
    logger.info(f"Password reset requested for {email}. Reset link: {reset_link}")


@router.post("/forgot-password", dependencies=[Depends(rate_limiter(limit=3, window=60))])
def forgot_password(
    data: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    user = get_user_by_email(db, data.email)
    
    # We return success even if user doesn't exist to prevent email enumeration
    if user:
        token = create_reset_token(user.email)
        background_tasks.add_task(send_reset_email, user.email, token)
        
    return {"message": "If that email is registered, you will receive a reset link shortly."}


@router.post("/reset-password", dependencies=[Depends(rate_limiter(limit=5, window=60))])
def reset_password(
    data: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    email = verify_reset_token(data.token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")
        
    user = get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=400, detail="User not found.")
        
    update_password(db, user.id, data.new_password)
    
    return {"message": "Password updated successfully."}