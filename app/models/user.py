import enum
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Enum as SQLEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.database import Base


class RoleType(enum.Enum):
    USER = "USER"
    ADMIN = "ADMIN"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    role = Column(
        SQLEnum(RoleType, name="role_type_enum"),
        nullable=False,
        default=RoleType.USER,
        server_default="USER",
    )

    first_name = Column(String, nullable=False)

    last_name = Column(String, nullable=False)

    email = Column(String, unique=True, nullable=False, index=True)

    hashed_password = Column(String, nullable=False)

    is_active = Column(Boolean, default=True)

    is_verified = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    conversations = relationship(
        "Conversation",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    wallet = relationship(
        "Wallet",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    ai_requests = relationship(
        "AIRequestLog",
        back_populates="user",
        cascade="all, delete-orphan",
    )