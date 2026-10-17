from dataclasses import dataclass
from typing import Dict, Optional

@dataclass
class SubscriptionPlan:
    id: str
    name: str
    price_ngn: int
    credits_per_month: int
    is_active: bool

@dataclass
class CreditPack:
    id: str
    name: str
    price_ngn: int
    credit_amount: int
    is_active: bool

SUBSCRIPTION_PLANS: Dict[str, SubscriptionPlan] = {
    "free": SubscriptionPlan(id="free", name="Free", price_ngn=0, credits_per_month=1000, is_active=True),
    "starter": SubscriptionPlan(id="starter", name="Starter", price_ngn=2500, credits_per_month=10000, is_active=True),
    "pro": SubscriptionPlan(id="pro", name="Pro", price_ngn=7500, credits_per_month=40000, is_active=True),
    "power": SubscriptionPlan(id="power", name="Power", price_ngn=15000, credits_per_month=100000, is_active=True),
}

CREDIT_PACKS: Dict[str, CreditPack] = {
    "credit_small": CreditPack(id="credit_small", name="Small", price_ngn=1500, credit_amount=5000, is_active=True),
    "credit_medium": CreditPack(id="credit_medium", name="Medium", price_ngn=5000, credit_amount=20000, is_active=True),
    "credit_large": CreditPack(id="credit_large", name="Large", price_ngn=10000, credit_amount=50000, is_active=True),
    "credit_mega": CreditPack(id="credit_mega", name="Mega", price_ngn=25000, credit_amount=150000, is_active=True),
}

def get_subscription_plan(plan_id: str) -> Optional[SubscriptionPlan]:
    return SUBSCRIPTION_PLANS.get(plan_id)

def get_credit_pack(pack_id: str) -> Optional[CreditPack]:
    return CREDIT_PACKS.get(pack_id)
