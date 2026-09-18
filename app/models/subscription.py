import enum
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Index
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class SubscriptionStatus(enum.Enum):
    ACTIVE = "ACTIVE"
    PAST_DUE = "PAST_DUE"
    CANCELED = "CANCELED"


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    plan_id = Column(String, nullable=False)
    status = Column(
        SQLEnum(SubscriptionStatus, name="subscription_status_enum"),
        nullable=False,
    )
    current_period_start = Column(DateTime(timezone=True), nullable=False)
    current_period_end = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user = relationship("User", backref="subscriptions")
    
    __table_args__ = (
        Index(
            'ix_active_subscription',
            'user_id',
            unique=True,
            postgresql_where=(status == SubscriptionStatus.ACTIVE),
            sqlite_where=(status == SubscriptionStatus.ACTIVE)
        ),
    )
