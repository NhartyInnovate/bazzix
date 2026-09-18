from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.user import UserCreate
from app.core.security import hash_password
from app.core.security import verify_password


def create_user(db: Session, user: UserCreate):
    db_user = User(
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        hashed_password=hash_password(user.password)
    )

    db.add(db_user)
    db.flush()

    from app.services.account_provisioning import provision_new_user_account
    provision_new_user_account(db, db_user.id)

    db.commit()
    db.refresh(db_user)

    return db_user




def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()


def authenticate_user(db: Session, email: str, password: str):
    user = get_user_by_email(db, email)

    if not user:
        return None

    if not verify_password(password, user.hashed_password):
        return None

    return user

def get_user_by_id(db: Session, user_id: int):
    return db.query(User).filter(User.id == user_id).first()

def update_password(db: Session, user_id: int, new_password: str):
    user = get_user_by_id(db, user_id)
    if user:
        user.hashed_password = hash_password(new_password)
        db.commit()
        db.refresh(user)
    return user