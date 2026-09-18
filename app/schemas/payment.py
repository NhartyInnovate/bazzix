from pydantic import BaseModel
from typing import Optional

class CheckoutRequest(BaseModel):
    product_id: str

class CheckoutResponse(BaseModel):
    authorization_url: str
    reference: str
    provider: str
