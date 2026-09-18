import unittest
from datetime import datetime, timezone
from typing import Optional

from app.services.payment import (
    PaymentProvider,
    PaymentInitializationResult,
    PaymentVerificationResult,
    PaymentProviderError,
    PaymentInitializationError,
    PaymentVerificationError,
    InvalidProviderResponseError
)


class MockPaymentProvider(PaymentProvider):
    """
    A fake payment provider implementation purely for testing the abstraction.
    Does NOT import or simulate Paystack APIs.
    """
    def initialize_transaction(
        self, 
        amount: int, 
        currency: str, 
        email: str, 
        reference: str
    ) -> PaymentInitializationResult:
        if amount <= 0:
            raise PaymentInitializationError("Amount must be greater than zero.")
        if currency != "NGN":
            raise PaymentInitializationError(f"Unsupported currency: {currency}")
            
        return PaymentInitializationResult(
            authorization_url=f"https://fake.provider.com/checkout/{reference}",
            provider_reference=reference,
            provider_transaction_id=f"tx_{reference}"
        )

    def verify_transaction(self, reference: str) -> PaymentVerificationResult:
        if reference == "fail_network":
            raise PaymentVerificationError("Network timeout.")
        if reference == "fail_response":
            raise InvalidProviderResponseError("Malformed JSON.")
            
        return PaymentVerificationResult(
            reference=reference,
            status="SUCCESS",
            amount=5000,
            currency="NGN",
            provider_transaction_id=f"tx_{reference}",
            paid_at=datetime.now(timezone.utc)
        )


class TestPaymentProviderAbstraction(unittest.TestCase):

    def setUp(self):
        self.provider = MockPaymentProvider()

    def test_initialization_success(self):
        result = self.provider.initialize_transaction(
            amount=5000,
            currency="NGN",
            email="test@example.com",
            reference="ref_123"
        )
        self.assertIsInstance(result, PaymentInitializationResult)
        self.assertEqual(result.authorization_url, "https://fake.provider.com/checkout/ref_123")
        self.assertEqual(result.provider_reference, "ref_123")

    def test_initialization_failure(self):
        with self.assertRaises(PaymentInitializationError):
            self.provider.initialize_transaction(
                amount=-100,
                currency="NGN",
                email="test@example.com",
                reference="ref_123"
            )
            
        with self.assertRaises(PaymentInitializationError):
            self.provider.initialize_transaction(
                amount=5000,
                currency="USD",
                email="test@example.com",
                reference="ref_123"
            )

    def test_verification_success(self):
        result = self.provider.verify_transaction("ref_123")
        self.assertIsInstance(result, PaymentVerificationResult)
        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.amount, 5000)
        self.assertEqual(result.currency, "NGN")
        # Ensure it is explicitly an integer without floating point representation
        self.assertTrue(isinstance(result.amount, int))

    def test_verification_exceptions(self):
        with self.assertRaises(PaymentVerificationError):
            self.provider.verify_transaction("fail_network")
            
        with self.assertRaises(InvalidProviderResponseError):
            self.provider.verify_transaction("fail_response")
            
        # Also ensure base class catches it
        with self.assertRaises(PaymentProviderError):
            self.provider.verify_transaction("fail_network")

