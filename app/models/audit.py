from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, JSON
from sqlalchemy.sql import func
from app.db.database import Base

class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    
    admin_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    
    target_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    
    target_user_email = Column(String, nullable=True)
    
    action = Column(String, nullable=False)
    
    details = Column(JSON, nullable=True)
    
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

