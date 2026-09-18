import enum
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class PurchaseStatus(enum.Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class Purchase(Base):
    __tablename__ = "purchases"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status = Column(
        SQLEnum(PurchaseStatus, name="purchase_status_enum"),
        nullable=False,
        default=PurchaseStatus.PENDING,
        server_default="PENDING",
    )

    product_id = Column(String, nullable=False)
    product_name_snapshot = Column(String, nullable=False)
    price_amount = Column(Integer, nullable=False)
    price_currency = Column(String, nullable=False)
    credit_allocation = Column(Integer, nullable=False)

    payment_provider = Column(String, nullable=False)
    payment_reference = Column(String, nullable=False)
    provider_transaction_id = Column(String, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    paid_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    user = relationship("User", backref="purchases")

    __table_args__ = (
        UniqueConstraint('payment_provider', 'payment_reference', name='uq_payment_provider_ref'),
    )
