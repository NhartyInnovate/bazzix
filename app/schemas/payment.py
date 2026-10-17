from pydantic import BaseModel
from typing import Optional

class CheckoutRequest(BaseModel):
    product_id: str

class CheckoutResponse(BaseModel):
    authorization_url: str
    reference: str
    provider: str

class PurchaseStatusResponse(BaseModel):
    reference: str
    status: str
    credit_amount: Optional[int] = None
    product_name: Optional[str] = None
