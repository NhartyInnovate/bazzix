from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import secrets
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from google.auth.exceptions import GoogleAuthError
from app.core.security import hash_password
from app.services.account_provisioning import provision_new_user_account
from app.schemas.auth import (
    LoginRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
    GoogleAuthRequest,
)
from app.core.auth import (
    create_access_token,
    create_reset_token,
    verify_reset_token,
    create_verification_token,
    verify_verification_token,
)
from app.crud.user import (
    authenticate_user,
    update_password,
    create_user,
    get_user_by_email,
    get_user_by_google_sub,
    get_user_by_id,
)
from app.db.dependencies import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.user import UserCreate
from app.core.rate_limit import rate_limiter
from app.services.email import (
    get_password_reset_template,
    get_welcome_template,
    get_email_verification_template,
)
from app.core.config import settings
import resend
import logging
import time
from collections import defaultdict

logger = logging.getLogger(__name__)

# In-memory sliding window cache for verification resend: user_id -> list of float timestamps
verification_resend_records: dict[int, list[float]] = defaultdict(list)


def check_verification_resend_rate_limit(user_id: int):
    now = time.time()
    timestamps = verification_resend_records[user_id]
    # Keep records within the last 1 hour (3600 seconds)
    timestamps = [t for t in timestamps if now - t < 3600]
    verification_resend_records[user_id] = timestamps

    # 1. Cooldown check: 1 request per 60 seconds
    if timestamps:
        elapsed = now - timestamps[-1]
        if elapsed < 60:
            wait_seconds = int(60 - elapsed) + 1
            raise HTTPException(
                status_code=429,
                detail=f"Please wait {wait_seconds} seconds before requesting another verification email.",
            )

    # 2. Hourly cap check: maximum 5 requests per hour (3600 seconds)
    if len(timestamps) >= 5:
        raise HTTPException(
            status_code=429,
            detail="Verification email limit reached. Please check your inbox or try again in an hour.",
        )


def record_verification_resend(user_id: int):
    verification_resend_records[user_id].append(time.time())


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
                "html": html_content,
            })
            logger.info(f"Successfully dispatched welcome email to {masked_email} via Resend")
        except Exception as e:
            logger.error(f"Failed to send welcome email to {masked_email}: {e}")
    else:
        logger.warning(f"RESEND_API_KEY is not set. Welcome email skipped for {masked_email}")


def send_verification_email(email: str, token: str):
    masked_email = _mask_email(email)
    logger.info(f"send_verification_email started for {masked_email}")

    verification_link = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    html_content = get_email_verification_template(verification_link)

    if settings.RESEND_API_KEY:
        try:
            resend.api_key = settings.RESEND_API_KEY
            response = resend.Emails.send({
                "from": "Bazzix <support@mail.nkaylabs.com>",
                "to": email,
                "subject": "Verify your Bazzix Email Address",
                "html": html_content,
            })
            resp_id = response.get("id") if isinstance(response, dict) else getattr(response, "id", "unknown")
            logger.info(f"Successfully dispatched verification email to {masked_email} via Resend. ID: {resp_id}")
        except Exception as e:
            logger.error(f"Failed to send verification email to {masked_email}: {e}")
    else:
        if settings.ENVIRONMENT == "production":
            logger.error(f"Failed to send verification email to {masked_email}: RESEND_API_KEY is missing in production.")
        else:
            logger.info(f"Local dev/test: verification email simulated for {masked_email}")


@router.post("/register", dependencies=[Depends(rate_limiter(limit=5, window=60))])
def register(user: UserCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    existing_user = get_user_by_email(db, user.email)

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered.",
        )

    created_user = create_user(db, user)
    verification_token = create_verification_token(created_user.id, created_user.email)

    background_tasks.add_task(send_welcome_email, created_user.email)
    background_tasks.add_task(send_verification_email, created_user.email, verification_token)

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


@router.post("/google", dependencies=[Depends(rate_limiter(limit=10, window=60))])
def google_auth(
    data: GoogleAuthRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    if not settings.GOOGLE_CLIENT_ID:
        logger.error("GOOGLE_CLIENT_ID is not configured.")
        raise HTTPException(
            status_code=500,
            detail="Google authentication is not configured.",
        )

    try:
        id_info = id_token.verify_oauth2_token(
            data.credential,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )
    except (ValueError, GoogleAuthError) as e:
        logger.warning(f"Google token verification failed: {type(e).__name__}")
        raise HTTPException(
            status_code=401,
            detail="Invalid Google credential.",
        )
    except Exception as e:
        logger.error(f"Unexpected error during Google token verification: {type(e).__name__}")
        raise HTTPException(
            status_code=401,
            detail="Invalid Google credential.",
        )

    # Validate issuer
    issuer = id_info.get("iss")
    if issuer not in ("accounts.google.com", "https://accounts.google.com"):
        logger.warning(f"Google token rejected due to unexpected issuer: {issuer}")
        raise HTTPException(
            status_code=401,
            detail="Invalid Google credential.",
        )

    # Validate audience
    if id_info.get("aud") != settings.GOOGLE_CLIENT_ID:
        logger.warning("Google token audience mismatch.")
        raise HTTPException(
            status_code=401,
            detail="Invalid Google credential.",
        )

    # Validate email claim
    email = id_info.get("email")
    if not email or not isinstance(email, str) or not email.strip():
        raise HTTPException(
            status_code=400,
            detail="Google account email is missing.",
        )
    email = email.strip().lower()

    # Validate email verification claim
    email_verified = id_info.get("email_verified")
    if not (email_verified is True or email_verified == "true"):
        raise HTTPException(
            status_code=400,
            detail="Google account email is not verified.",
        )

    # Validate Google subject identifier
    google_sub = id_info.get("sub")
    if not google_sub or not isinstance(google_sub, str) or not google_sub.strip():
        raise HTTPException(
            status_code=400,
            detail="Google account identifier is missing.",
        )
    google_sub = google_sub.strip()

    if data.mode == "register":
        # Check if an account already exists with this email or Google sub
        existing_user = get_user_by_email(db, email)
        if not existing_user:
            existing_user = get_user_by_google_sub(db, google_sub)

        if existing_user:
            logger.info(f"Google registration rejected: account already exists for {email}")
            raise HTTPException(
                status_code=409,
                detail="An account with this email already exists. Please sign in instead.",
            )

        # Extract names from Google claims
        given_name = (id_info.get("given_name") or "").strip()
        family_name = (id_info.get("family_name") or "").strip()
        if not given_name:
            full_name = (id_info.get("name") or "").strip()
            if full_name:
                parts = full_name.split(" ", 1)
                given_name = parts[0]
                if len(parts) > 1 and not family_name:
                    family_name = parts[1]
            else:
                given_name = email.split("@")[0]

        # Generate a high-entropy random password to fulfill NOT NULL database constraint
        random_password = secrets.token_urlsafe(64)
        hashed_pwd = hash_password(random_password)

        new_user = User(
            first_name=given_name,
            last_name=family_name,
            email=email,
            google_sub=google_sub,
            hashed_password=hashed_pwd,
            is_active=True,
            is_verified=True,
        )

        try:
            db.add(new_user)
            db.flush()
            provision_new_user_account(db, new_user.id)
            db.commit()
            db.refresh(new_user)
            user = new_user
            background_tasks.add_task(send_welcome_email, user.email)
            logger.info(f"Created and provisioned new user via Google auth for user_id={user.id}")
        except IntegrityError:
            db.rollback()
            # If concurrent registration created the account, report that it already exists
            raise HTTPException(
                status_code=409,
                detail="An account with this email already exists. Please sign in instead.",
            )
        except Exception:
            db.rollback()
            raise

    elif data.mode == "login":
        user_by_email = get_user_by_email(db, email)
        user_by_sub = get_user_by_google_sub(db, google_sub)

        if not user_by_email and not user_by_sub:
            # Never automatically create an account during Google sign-in
            logger.info(f"Google sign-in rejected: no account found for {email}")
            raise HTTPException(
                status_code=404,
                detail="No Bazzix account found for this Google email. Please create an account first.",
            )

        if user_by_email:
            # Do not link an existing email/password account solely because its email matches
            if not user_by_email.google_sub:
                logger.warning(f"Google sign-in blocked: account {email} uses password authentication and is not linked.")
                raise HTTPException(
                    status_code=409,
                    detail="This account was registered with an email and password. Please sign in with your email and password.",
                )
            if user_by_email.google_sub != google_sub:
                logger.warning(f"Google sign-in blocked: sub mismatch for {email}.")
                raise HTTPException(
                    status_code=401,
                    detail="Google account identity mismatch.",
                )
            user = user_by_email
        else:
            user = user_by_sub

        if not user.is_active:
            raise HTTPException(
                status_code=403,
                detail="Account is disabled. Please contact support.",
            )

        if not user.is_verified:
            try:
                user.is_verified = True
                db.commit()
                db.refresh(user)
                logger.info(f"Verified existing user account via Google auth for user_id={user.id}")
            except Exception:
                db.rollback()
                raise
    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid authentication mode.",
        )

    token = create_access_token({"sub": str(user.id)})
    return {
        "access_token": token,
        "token_type": "bearer",
    }


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
                "html": html_content,
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
    db: Session = Depends(get_db),
):
    if settings.ENVIRONMENT == "production" and not settings.RESEND_API_KEY:
        logger.error("RESEND_API_KEY is missing in production. Cannot process password reset.")
        raise HTTPException(
            status_code=500,
            detail="Password reset is currently unavailable due to a server configuration error.",
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
    db: Session = Depends(get_db),
):
    email = verify_reset_token(data.token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

    user = get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=400, detail="User not found.")

    update_password(db, user.id, data.new_password)

    return {"message": "Password updated successfully."}


@router.post("/verify-email", dependencies=[Depends(rate_limiter(limit=10, window=60))])
def verify_email(
    data: VerifyEmailRequest,
    db: Session = Depends(get_db),
):
    payload = verify_verification_token(data.token)
    if not payload:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired verification token.",
        )

    user = get_user_by_id(db, payload["user_id"])
    if not user:
        raise HTTPException(
            status_code=400,
            detail="User not found.",
        )

    if user.email.lower() != payload["email"].lower():
        raise HTTPException(
            status_code=400,
            detail="Verification token is not valid for this account email.",
        )

    if user.is_verified:
        return {
            "message": "Email is already verified.",
            "is_verified": True,
        }

    user.is_verified = True
    db.commit()
    db.refresh(user)

    logger.info(f"Email verified successfully for user_id={user.id}")

    return {
        "message": "Email verified successfully.",
        "is_verified": True,
    }


@router.post("/resend-verification", dependencies=[Depends(rate_limiter(limit=10, window=60))])
def resend_verification(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    if current_user.is_verified:
        return {
            "message": "Your email is already verified.",
            "is_verified": True,
        }

    check_verification_resend_rate_limit(current_user.id)
    record_verification_resend(current_user.id)

    token = create_verification_token(current_user.id, current_user.email)
    background_tasks.add_task(send_verification_email, current_user.email, token)

    return {
        "message": "Verification email sent. Please check your inbox.",
        "is_verified": False,
    }