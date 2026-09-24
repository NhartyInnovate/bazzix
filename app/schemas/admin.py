from pydantic import BaseModel, EmailStr
from typing import Optional, List, Any
from datetime import datetime

class AdminStatsResponse(BaseModel):
    total_users: int
    active_users: int
    total_ai_requests: int
    successful_ai_requests: int
    failed_ai_requests: int
    total_provider_cost: float
    total_credits_consumed: int
    total_successful_purchases: int
    total_purchase_revenue: float

class AdminUserSummary(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: EmailStr
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    available_credits: int

class AdminUserListResponse(BaseModel):
    users: List[AdminUserSummary]
    total: int
    page: int
    size: int

class AdminUserDetail(AdminUserSummary):
    subscription_balance: int
    purchased_balance: int
    reserved_balance: int
    conversations_count: int

class AIUsageItem(BaseModel):
    id: int
    model: str
    request_tokens: Optional[int]
    response_tokens: Optional[int]
    total_tokens: Optional[int]
    provider_cost: Optional[float]
    credits_charged: Optional[int]
    status: str
    created_at: datetime

class AIUsageListResponse(BaseModel):
    items: List[AIUsageItem]
    total: int
    page: int
    size: int

class PurchaseItem(BaseModel):
    id: int
    product_id: str
    price_amount: int
    price_currency: str
    credit_allocation: int
    payment_reference: str
    status: str
    created_at: datetime

class PurchaseListResponse(BaseModel):
    items: List[PurchaseItem]
    total: int
    page: int
    size: int

class LedgerItem(BaseModel):
    id: int
    amount: int
    transaction_type: str
    reference_id: Optional[str]
    created_at: datetime

class LedgerListResponse(BaseModel):
    items: List[LedgerItem]
    total: int
    page: int
    size: int

class CreditAdjustmentRequest(BaseModel):
    amount: int
    reason: str

class CreditAdjustmentResponse(BaseModel):
    status: str
    transaction_id: int
    new_balance: int

class AuditLogItem(BaseModel):
    id: int
    admin_user_id: int
    target_user_id: Optional[int]
    target_user_email: Optional[str]
    action: str
    details: Optional[Any]
    created_at: datetime

class AuditLogListResponse(BaseModel):
    items: List[AuditLogItem]
    total: int
    page: int
    size: int

class AdminHealthResponse(BaseModel):
    status: str
    database: str
    openai_configured: bool
    paystack_configured: bool
    resend_configured: bool
