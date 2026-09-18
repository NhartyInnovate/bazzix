import enum
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Numeric, UniqueConstraint
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class UsageSource(enum.Enum):
    PROVIDER = "PROVIDER"
    ESTIMATED_PARTIAL = "ESTIMATED_PARTIAL"


class RequestStatus(enum.Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class AIRequestLog(Base):
    __tablename__ = "ai_request_logs"

    id = Column(Integer, primary_key=True, index=True)
    
    client_request_id = Column(String, index=True, nullable=False)
    
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    conversation_id = Column(
        Integer,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    provider = Column(String, nullable=False, default="openai")
    model = Column(String, nullable=False)
    
    provider_request_id = Column(String, nullable=True)
    
    prompt_tokens = Column(Integer, nullable=True)
    cached_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    
    usage_source = Column(
        SQLEnum(UsageSource, name="usage_source_enum"),
        nullable=True,
    )
    
    provider_cost = Column(Numeric(12, 8), nullable=True)
    
    status = Column(
        SQLEnum(RequestStatus, name="request_status_enum"),
        nullable=False,
        default=RequestStatus.PENDING,
    )
    
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("user_id", "client_request_id", name="uq_user_client_request"),
    )

    user = relationship("User", back_populates="ai_requests")
    conversation = relationship("Conversation", back_populates="ai_requests")
