from datetime import datetime, timedelta, timezone
from app.core.config import settings
from jose import jwt, JWTError


def _get_secret_key() -> str:
    return settings.SECRET_KEY or "bazzix-default-secret-key-for-jwt-signing"


def create_access_token(data: dict):
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire})

    return jwt.encode(
        to_encode,
        _get_secret_key(),
        algorithm=settings.ALGORITHM,
    )


def verify_access_token(token: str):
    try:
        payload = jwt.decode(
            token,
            _get_secret_key(),
            algorithms=[settings.ALGORITHM],
        )
        if payload.get("type") in ("reset", "verification"):
            return None
        return payload
    except JWTError:
        return None


def create_reset_token(email: str):
    expire = datetime.now(timezone.utc) + timedelta(minutes=30)
    to_encode = {"sub": email, "type": "reset", "exp": expire}
    return jwt.encode(to_encode, _get_secret_key(), algorithm=settings.ALGORITHM)


def verify_reset_token(token: str):
    try:
        payload = jwt.decode(token, _get_secret_key(), algorithms=[settings.ALGORITHM])
        if payload.get("type") != "reset":
            return None
        return payload.get("sub")
    except JWTError:
        return None


def create_verification_token(user_id: int, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=24)
    to_encode = {
        "sub": str(user_id),
        "email": email,
        "type": "verification",
        "exp": expire,
    }
    return jwt.encode(to_encode, _get_secret_key(), algorithm=settings.ALGORITHM)


def verify_verification_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(
            token,
            _get_secret_key(),
            algorithms=[settings.ALGORITHM],
        )
        if payload.get("type") != "verification":
            return None
        sub = payload.get("sub")
        email = payload.get("email")
        if not sub or not email:
            return None
        return {
            "user_id": int(sub),
            "email": str(email),
        }
    except (JWTError, ValueError):
        return None