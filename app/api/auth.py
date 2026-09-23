from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.schemas.auth import LoginRequest, ForgotPasswordRequest, ResetPasswordRequest
from app.core.auth import create_access_token, create_reset_token, verify_reset_token
from app.crud.user import authenticate_user, update_password
from app.crud.user import create_user, get_user_by_email
from app.db.dependencies import get_db
from app.schemas.user import UserCreate
from app.core.rate_limit import rate_limiter
import resend
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

def _mask_email(email: str) -> str:
    try:
        parts = email.split("@")
        if len(parts) == 2:
            return f"{parts[0][0]}***@{parts[1]}"
    except Exception:
        pass
    return "***@***"


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post("/register", dependencies=[Depends(rate_limiter(limit=5, window=60))])

def send_welcome_email(email: str):
    masked_email = _mask_email(email)
    logger.info(f"send_welcome_email started for {masked_email}")
    
    dashboard_link = f"{settings.FRONTEND_URL}/dashboard"
    html_content = get_welcome_template(dashboard_link, settings.FRONTEND_URL)
    
    if settings.RESEND_API_KEY:
        try:
            resend.api_key = settings.RESEND_API_KEY
            response = resend.Emails.send({
                "from": "Bazzix <support@mail.nkaylabs.com>",
                "to": email,
                "subject": "Welcome to Bazzix",
                "html": html_content
            })
            logger.info(f"Successfully dispatched welcome email to {masked_email} via Resend")
        except Exception as e:
            logger.error(f"Failed to send welcome email to {masked_email}: {e}")
    else:
        logger.warning(f"RESEND_API_KEY is not set. Welcome email skipped for {masked_email}")


def register(user: UserCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    existing_user = get_user_by_email(db, user.email)

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered."
        )
    
    created_user = create_user(db, user)
    background_tasks.add_task(send_welcome_email, created_user.email)

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


from app.services.email import get_password_reset_template, get_welcome_template

def send_reset_email(email: str, token: str):
    masked_email = _mask_email(email)
    logger.warning(f"DIAGNOSTIC: send_reset_email started for {masked_email}")
    
    reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    html_content = get_password_reset_template(reset_link)
    logger.warning(f"DIAGNOSTIC: Template constructed for {masked_email}")
    
    if settings.RESEND_API_KEY:
        try:
            resend.api_key = settings.RESEND_API_KEY
            logger.warning(f"DIAGNOSTIC: Attempting Resend API call for {masked_email}")
            
            response = resend.Emails.send({
                "from": "Bazzix <support@mail.nkaylabs.com>",
                "to": email,
                "subject": "Reset your Bazzix Password",
                "html": html_content
            })
            
            resp_id = response.get("id") if isinstance(response, dict) else getattr(response, "id", "unknown")
            logger.warning(f"DIAGNOSTIC: Resend API call succeeded for {masked_email}. Response ID: {resp_id}")
            logger.info(f"Successfully dispatched password reset email to {email} via Resend")
            
        except Exception as e:
            exception_type = type(e).__name__
            safe_message = str(e)
            logger.error(f"DIAGNOSTIC: Resend email dispatch failed at API call for {masked_email}. Type: {exception_type}, Message: {safe_message}")
    else:
        if settings.ENVIRONMENT == "production":
            logger.error(f"Failed to send email to {email}: RESEND_API_KEY is missing in production.")
        else:
            # Fallback for local development when no API key is provided
            print("\n" + "="*50)
            print(f"PASSWORD RESET REQUESTED FOR: {email}")
            print(f"RESET LINK: {reset_link}")
            print("="*50 + "\n")


@router.post("/forgot-password", dependencies=[Depends(rate_limiter(limit=3, window=60))])
def forgot_password(
    data: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    if settings.ENVIRONMENT == "production" and not settings.RESEND_API_KEY:
        logger.error("RESEND_API_KEY is missing in production. Cannot process password reset.")
        raise HTTPException(
            status_code=500,
            detail="Password reset is currently unavailable due to a server configuration error."
        )

    user = get_user_by_email(db, data.email)
    masked_email = _mask_email(data.email)
    
    # We return success even if user doesn't exist to prevent email enumeration
    if user:
        token = create_reset_token(user.email)
        logger.warning(f"DIAGNOSTIC: User found. Registering password reset task for {masked_email}")
        background_tasks.add_task(send_reset_email, user.email, token)
        logger.warning(f"DIAGNOSTIC: Password reset task registered for {masked_email}")
    else:
        logger.warning(f"DIAGNOSTIC: User not found for password reset request: {masked_email}")
        
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