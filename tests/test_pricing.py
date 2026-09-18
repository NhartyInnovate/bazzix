import unittest
from decimal import Decimal
from app.services.pricing import calculate_cost, DUMMY_PROVIDER_REGISTRY, ProviderPricingConfig, DUMMY_COMMERCIAL_POLICY
from app.models.ledger import TransactionType

class TestPricingService(unittest.TestCase):
    
    def setUp(self):
        # Inject a deterministic mock configuration for strict unit testing
        DUMMY_PROVIDER_REGISTRY["mock_provider"] = {
            "mock_model": ProviderPricingConfig(
                prompt_token_cost=Decimal('0.01'),
                completion_token_cost=Decimal('0.05'),
                cached_token_cost=Decimal('0.005'),
            )
        }
        DUMMY_COMMERCIAL_POLICY.credit_exchange_rate = Decimal('10.0')

    def test_pricing_calculation_standard(self):
        result = calculate_cost("mock_provider", "mock_model", 10, 5)
        # Cost: (10 * 0.01) + (5 * 0.05) = 0.10 + 0.25 = 0.35
        # Credits: ceil(0.35 * 10) = 4
        self.assertEqual(result.provider_cost, Decimal('0.35'))
        self.assertEqual(result.bazzix_credits, 4)

    def test_pricing_calculation_with_cached(self):
        result = calculate_cost("mock_provider", "mock_model", prompt_tokens=10, completion_tokens=5, cached_tokens=4)
        # Uncached prompt: 6 * 0.01 = 0.06
        # Cached prompt: 4 * 0.005 = 0.02
        # Completion: 5 * 0.05 = 0.25
        # Total cost: 0.33
        # Credits: ceil(0.33 * 10) = ceil(3.3) = 4
        self.assertEqual(result.provider_cost, Decimal('0.33'))
        self.assertEqual(result.bazzix_credits, 4)

    def test_pricing_zero_edge_case(self):
        result = calculate_cost("mock_provider", "mock_model", 0, 0, 0)
        self.assertEqual(result.provider_cost, Decimal('0.0'))
        self.assertEqual(result.bazzix_credits, 0)

    def test_negative_tokens_rejected(self):
        with self.assertRaises(ValueError):
            calculate_cost("mock_provider", "mock_model", -5, 10)

    def test_unknown_model_rejected(self):
        with self.assertRaises(ValueError):
            calculate_cost("openai", "gpt-99-unknown", 10, 10)

    def test_reservation_release_enum(self):
        # Verify the enum was correctly updated
        self.assertTrue(hasattr(TransactionType, "RESERVATION_RELEASE"))
        self.assertEqual(TransactionType.RESERVATION_RELEASE.value, "RESERVATION_RELEASE")

if __name__ == '__main__':
    unittest.main()
