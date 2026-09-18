from decimal import Decimal, ROUND_UP
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
    credits_per_usd: Decimal
    commercial_multiplier: Decimal
    minimum_charge: int


# Production registry for provider pricing
PROVIDER_REGISTRY = {
    "openai": {
        "gpt-4.1-mini": ProviderPricingConfig(
            prompt_token_cost=Decimal('0.000000400'),       # $0.40 / 1M
            cached_token_cost=Decimal('0.000000100'),       # $0.10 / 1M
            completion_token_cost=Decimal('0.000001600'),   # $1.60 / 1M
        ),
    }
}

# Configured Bazzix Commercial Policy
BAZZIX_POLICY = BazzixCommercialPolicy(
    credits_per_usd=Decimal('1000.0'),
    commercial_multiplier=Decimal('10.0'),
    minimum_charge=10
)


def get_provider_pricing(provider: str, model: str) -> ProviderPricingConfig:
    provider_config = PROVIDER_REGISTRY.get(provider, {})
    if model in provider_config:
        return provider_config[model]
    raise ValueError(f"Unknown pricing configuration for provider '{provider}' and model '{model}'")

def get_commercial_policy() -> BazzixCommercialPolicy:
    return BAZZIX_POLICY

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
    if total_provider_cost > 0:
        bazzix_usage_value = total_provider_cost * commercial_policy.commercial_multiplier
        raw_credits = bazzix_usage_value * commercial_policy.credits_per_usd

        # Financially conservative rounding: ROUND_UP to the nearest whole credit using Decimal
        bazzix_credits = int(raw_credits.quantize(Decimal('1.'), rounding=ROUND_UP))

        # Apply minimum charge for successful requests
        bazzix_credits = max(bazzix_credits, commercial_policy.minimum_charge)
    else:
        bazzix_credits = 0

    return PricingResult(
        provider_cost=total_provider_cost,
        bazzix_credits=bazzix_credits
    )
