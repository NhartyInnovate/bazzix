from sqlalchemy import Column, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True, index=True)
    
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    
    subscription_balance = Column(Integer, nullable=False, default=0)
    purchased_balance = Column(Integer, nullable=False, default=0)
    reserved_balance = Column(Integer, nullable=False, default=0)
    
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user = relationship(
        "User",
        back_populates="wallet",
    )
    
    transactions = relationship(
        "LedgerTransaction",
        back_populates="wallet",
        cascade="all, delete-orphan",
    )

    @property
    def available_credits(self) -> int:
        return (self.subscription_balance + self.purchased_balance) - self.reserved_balance
