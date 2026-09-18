import unittest
from unittest.mock import patch, Mock
from datetime import datetime, timezone

from app.services.paystack import PaystackProvider
from app.services.payment import (
    PaymentInitializationResult,
    PaymentVerificationResult,
    PaymentInitializationError,
    PaymentVerificationError,
    InvalidProviderResponseError
)


class TestPaystackProvider(unittest.TestCase):
    def setUp(self):
        self.provider = PaystackProvider(secret_key="sk_test_fake123")

    @patch("app.services.paystack.requests.post")
    def test_initialize_transaction_success(self, mock_post):
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "status": True,
            "message": "Authorization URL created",
            "data": {
                "authorization_url": "https://checkout.paystack.com/fake123",
                "access_code": "fake123",
                "reference": "tx-12345"
            }
        }
        mock_post.return_value = mock_response

        # 1500 NGN
        result = self.provider.initialize_transaction(
            amount=1500,
            currency="NGN",
            email="test@example.com",
            reference="tx-12345"
        )

        # Check request
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://api.paystack.co/transaction/initialize")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer sk_test_fake123")
        
        # Verify amount is exactly converted to kobo
        self.assertEqual(kwargs["json"]["amount"], 150000)
        self.assertEqual(kwargs["json"]["currency"], "NGN")

        # Check result
        self.assertIsInstance(result, PaymentInitializationResult)
        self.assertEqual(result.authorization_url, "https://checkout.paystack.com/fake123")
        self.assertEqual(result.provider_reference, "tx-12345")

    @patch("app.services.paystack.requests.post")
    def test_initialize_money_amounts(self, mock_post):
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "status": True,
            "data": {"authorization_url": "url", "reference": "ref"}
        }
        mock_post.return_value = mock_response

        self.provider.initialize_transaction(5000, "NGN", "t@e.com", "ref-5000")
        self.assertEqual(mock_post.call_args[1]["json"]["amount"], 500000)

        self.provider.initialize_transaction(25000, "NGN", "t@e.com", "ref-25000")
        self.assertEqual(mock_post.call_args[1]["json"]["amount"], 2500000)

    def test_initialize_validation_errors(self):
        # Negative amount
        with self.assertRaises(PaymentInitializationError):
            self.provider.initialize_transaction(-5000, "NGN", "test@example.com", "ref_1")
            
        # Zero amount
        with self.assertRaises(PaymentInitializationError):
            self.provider.initialize_transaction(0, "NGN", "test@example.com", "ref_1")
            
        # Float amount
        with self.assertRaises(PaymentInitializationError):
            self.provider.initialize_transaction(1500.50, "NGN", "test@example.com", "ref_1")

        # Invalid reference
        with self.assertRaises(PaymentInitializationError):
            self.provider.initialize_transaction(1500, "NGN", "test@example.com", "ref space")

    @patch("app.services.paystack.requests.post")
    def test_initialize_http_errors(self, mock_post):
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 400
        mock_post.return_value = mock_response

        with self.assertRaises(PaymentInitializationError) as context:
            self.provider.initialize_transaction(1500, "NGN", "a@b.com", "ref")
        self.assertIn("status 400", str(context.exception))
        
        # Ensure secret key is not in exception string
        self.assertNotIn("sk_test", str(context.exception))

    @patch("app.services.paystack.requests.get")
    def test_verify_transaction_success(self, mock_get):
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "status": True,
            "message": "Verification successful",
            "data": {
                "id": 123456789,
                "status": "success",
                "reference": "tx-12345",
                "amount": 150000, # kobo
                "currency": "NGN",
                "paid_at": "2023-01-01T12:30:00.000Z"
            }
        }
        mock_get.return_value = mock_response

        result = self.provider.verify_transaction("tx-12345")

        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertEqual(args[0], "https://api.paystack.co/transaction/verify/tx-12345")
        
        self.assertIsInstance(result, PaymentVerificationResult)
        self.assertEqual(result.status, "success")
        # Reverse conversion from kobo to NGN
        self.assertEqual(result.amount, 1500)
        self.assertTrue(isinstance(result.amount, int))
        self.assertEqual(result.currency, "NGN")
        self.assertEqual(result.provider_transaction_id, "123456789")
        self.assertEqual(result.paid_at.year, 2023)
        self.assertEqual(result.paid_at.minute, 30)

    @patch("app.services.paystack.requests.get")
    def test_verify_malformed_response(self, mock_get):
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "status": True,
            "data": {} # Missing required fields
        }
        mock_get.return_value = mock_response

        with self.assertRaises(InvalidProviderResponseError):
            self.provider.verify_transaction("tx-12345")

    def test_verify_invalid_reference(self):
        with self.assertRaises(PaymentVerificationError):
            self.provider.verify_transaction("inv@lid-ref!")
            
    def test_provider_initialization_no_key(self):
        with self.assertRaises(ValueError):
            PaystackProvider(secret_key="")

