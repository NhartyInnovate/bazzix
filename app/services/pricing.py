from decimal import Decimal
from dataclasses import dataclass
from typing import Optional

# 1. Provider Cost Data
@dataclass
class ProviderPricingConfig:
    # Costs expressed in USD per 1 token
    prompt_token_cost: Decimal
    completion_token_cost: Decimal
    cached_token_cost: Optional[Decimal] = None


# 2. Bazzix Commercial Policy
@dataclass
class BazzixCommercialPolicy:
    # How many provider cost fiat units equal 1 Bazzix Credit?
    credit_exchange_rate: Decimal


# Dummy registries for testing ONLY. Actual values must be configured by product owners later.
DUMMY_PROVIDER_REGISTRY = {
    "openai": {
        "gpt-4.1-mini": ProviderPricingConfig(
            prompt_token_cost=Decimal('0.000000150'),
            cached_token_cost=Decimal('0.000000075'),
            completion_token_cost=Decimal('0.000000600'),
        ),
        "gpt-4o-mini": ProviderPricingConfig(
            prompt_token_cost=Decimal('0.000000150'),
            cached_token_cost=Decimal('0.000000075'),
            completion_token_cost=Decimal('0.000000600'),
        ),
    }
}

# Dummy commercial policy for testing ONLY.
DUMMY_COMMERCIAL_POLICY = BazzixCommercialPolicy(
    credit_exchange_rate=Decimal('100.0') # 1 Credit = $0.01 provider cost (example)
)


def get_provider_pricing(provider: str, model: str) -> ProviderPricingConfig:
    provider_config = DUMMY_PROVIDER_REGISTRY.get(provider, {})
    if model in provider_config:
        return provider_config[model]
    raise ValueError(f"Unknown pricing configuration for provider '{provider}' and model '{model}'")

def get_commercial_policy() -> BazzixCommercialPolicy:
    return DUMMY_COMMERCIAL_POLICY

@dataclass
class PricingResult:
    provider_cost: Decimal
    bazzix_credits: int

def calculate_cost(
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    cached_tokens: int = 0
) -> PricingResult:
    """
    Calculates exact provider cost (Decimal) and derived Bazzix Credits (Integer).
    Returns 0 if usage is missing or 0.
    """
    if prompt_tokens < 0 or completion_tokens < 0 or cached_tokens < 0:
        raise ValueError("Token counts cannot be negative.")
        
    provider_config = get_provider_pricing(provider, model)
    commercial_policy = get_commercial_policy()
    
    # 1. Calculate Provider Cost
    actual_cached = cached_tokens if provider_config.cached_token_cost is not None else 0
    actual_uncached_prompt = max(0, prompt_tokens - actual_cached)
    
    cost_prompt = Decimal(actual_uncached_prompt) * provider_config.prompt_token_cost
    cost_cached = Decimal(actual_cached) * (provider_config.cached_token_cost or Decimal('0'))
    cost_completion = Decimal(completion_tokens) * provider_config.completion_token_cost
    
    total_provider_cost = cost_prompt + cost_cached + cost_completion
    
    # 2. Calculate Bazzix Credits
    import math
    if total_provider_cost > 0:
        raw_credits = total_provider_cost * commercial_policy.credit_exchange_rate
        bazzix_credits = math.ceil(raw_credits)
    else:
        bazzix_credits = 0
        
    return PricingResult(
        provider_cost=total_provider_cost,
        bazzix_credits=bazzix_credits
    )
