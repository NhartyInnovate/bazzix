import unittest
from decimal import Decimal
from app.services.pricing import calculate_cost, PROVIDER_REGISTRY, ProviderPricingConfig, BAZZIX_POLICY
from app.models.ledger import TransactionType

class TestPricingService(unittest.TestCase):

    def setUp(self):
        # Inject a deterministic mock configuration for strict unit testing
        PROVIDER_REGISTRY["mock_provider"] = {
            "mock_model": ProviderPricingConfig(
                prompt_token_cost=Decimal('0.01'),
                completion_token_cost=Decimal('0.05'),
                cached_token_cost=Decimal('0.005'),
            )
        }

        # Reset BAZZIX_POLICY to default values for tests
        BAZZIX_POLICY.credits_per_usd = Decimal('1000.0')
        BAZZIX_POLICY.commercial_multiplier = Decimal('10.0')
        BAZZIX_POLICY.minimum_charge = 10

    def test_pricing_calculation_minimum_charge(self):
        # Small usage: 10 prompt, 5 completion
        # Cost: (10 * 0.01) + (5 * 0.05) = 0.10 + 0.25 = 0.35
        # Value: 0.35 * 10.0 = 3.5
        # Raw Credits: 3.5 * 1000.0 = 3500 (Way above minimum!)

        # Let's use tiny usage to test minimum charge
        # 1 prompt, 0 completion
        # Cost: 0.01
        # Value: 0.1
        # Raw credits: 100
        # Still above minimum! We need even tinier usage.

        # Let's adjust mock pricing for this test
        PROVIDER_REGISTRY["mock_provider"]["mock_model"].prompt_token_cost = Decimal('0.0001')
        result = calculate_cost("mock_provider", "mock_model", 1, 0)
        # Cost: 0.0001
        # Value: 0.001
        # Credits: 0.001 * 1000 = 1 credit.
        # This is below minimum, so it should be rounded up to 10.
        self.assertEqual(result.provider_cost, Decimal('0.0001'))
        self.assertEqual(result.bazzix_credits, 10)

    def test_pricing_calculation_above_minimum(self):
        result = calculate_cost("mock_provider", "mock_model", 10, 5)
        # Cost: 0.10 + 0.25 = 0.35
        # Credits: 0.35 * 10.0 * 1000.0 = 3500
        self.assertEqual(result.provider_cost, Decimal('0.35'))
        self.assertEqual(result.bazzix_credits, 3500)

    def test_pricing_fractional_rounding(self):
        # Test rounding UP
        # Cost: 0.00011 -> 0.00011 * 10 * 1000 = 1.1 -> rounds up to 2, but wait, minimum is 10.
        # Let's disable minimum to test rounding explicitly
        BAZZIX_POLICY.minimum_charge = 0
        PROVIDER_REGISTRY["mock_provider"]["mock_model"].prompt_token_cost = Decimal('0.00011')

        result = calculate_cost("mock_provider", "mock_model", 1, 0)
        self.assertEqual(result.provider_cost, Decimal('0.00011'))
        # 0.00011 * 10000 = 1.1. Round up -> 2
        self.assertEqual(result.bazzix_credits, 2)

    def test_pricing_calculation_with_cached(self):
        result = calculate_cost("mock_provider", "mock_model", prompt_tokens=10, completion_tokens=5, cached_tokens=4)
        # Uncached prompt: 6 * 0.01 = 0.06
        # Cached prompt: 4 * 0.005 = 0.02
        # Completion: 5 * 0.05 = 0.25
        # Total cost: 0.33
        # Credits: 0.33 * 10 * 1000 = 3300
        self.assertEqual(result.provider_cost, Decimal('0.33'))
        self.assertEqual(result.bazzix_credits, 3300)

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

    def test_commercial_multiplier_independence(self):
        # 9. Changing the commercial multiplier changes Bazzix Credits without changing provider pricing.
        res1 = calculate_cost("mock_provider", "mock_model", 10, 5)

        BAZZIX_POLICY.commercial_multiplier = Decimal('20.0')
        res2 = calculate_cost("mock_provider", "mock_model", 10, 5)

        self.assertEqual(res1.provider_cost, res2.provider_cost)
        self.assertEqual(res2.bazzix_credits, res1.bazzix_credits * 2)

    def test_reservation_release_enum(self):
        # Verify the enum was correctly updated
        self.assertTrue(hasattr(TransactionType, "RESERVATION_RELEASE"))
        self.assertEqual(TransactionType.RESERVATION_RELEASE.value, "RESERVATION_RELEASE")

if __name__ == '__main__':
    unittest.main()
