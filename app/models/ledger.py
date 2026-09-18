import enum
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class TransactionType(enum.Enum):
    RESERVATION = "RESERVATION"
    CHARGE = "CHARGE"
    REFUND = "REFUND"
    SIGNUP_BONUS = "SIGNUP_BONUS"
    PURCHASE = "PURCHASE"
    ADJUSTMENT = "ADJUSTMENT"
    RESERVATION_RELEASE = "RESERVATION_RELEASE"


class LedgerTransaction(Base):
    __tablename__ = "ledger_transactions"

    id = Column(Integer, primary_key=True, index=True)
    
    wallet_id = Column(
        Integer,
        ForeignKey("wallets.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    amount = Column(Integer, nullable=False)
    
    transaction_type = Column(
        SQLEnum(TransactionType, name="transaction_type_enum"),
        nullable=False,
    )
    
    reference_id = Column(String, index=True, nullable=True)
    
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    wallet = relationship(
        "Wallet",
        back_populates="transactions",
    )
