from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.schemas.auth import LoginRequest
from app.core.auth import create_access_token
from app.crud.user import authenticate_user
from app.crud.user import create_user, get_user_by_email
from app.db.dependencies import get_db
from app.schemas.user import UserCreate, LoginRequest
from app.core.rate_limit import rate_limiter


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