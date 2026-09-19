import unittest
from unittest.mock import patch, Mock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.database import Base
from app.db.dependencies import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.purchase import Purchase, PurchaseStatus
from app.models.wallet import Wallet
from app.models.ledger import LedgerTransaction
from app.services.payment import PaymentInitializationResult, PaymentInitializationError


from sqlalchemy.pool import StaticPool

class TestCheckoutAPI(unittest.TestCase):
    def setUp(self):
        # Setup in-memory DB for Purchase saving
        self.engine = create_engine(
            'sqlite:///:memory:', 
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = self.SessionLocal()

        self.user = User(
            id=1,
            first_name="Test",
            last_name="User",
            email="test@example.com",
            hashed_password="pw",
            is_active=True
        )
        self.db.add(self.user)
        self.db.commit()

        # Dependency Overrides
        def override_get_db():
            try:
                yield self.db
            finally:
                self.db.close()

        def override_get_current_user():
            return self.user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        Base.metadata.drop_all(self.engine)

    @patch("app.api.payments.PaystackProvider")
    def test_checkout_success(self, mock_provider_class):
        # Mock the provider instance
        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider
        
        mock_provider.initialize_transaction.return_value = PaymentInitializationResult(
            authorization_url="https://checkout.paystack.com/fake123",
            provider_reference="bazzix_fake_uuid",
            provider_transaction_id=None
        )

        response = self.client.post("/api/payments/checkout", json={
            "product_id": "credit_small"
        })

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["authorization_url"], "https://checkout.paystack.com/fake123")
        self.assertEqual(data["reference"], "bazzix_fake_uuid")
        self.assertEqual(data["provider"], "paystack")

        # Verify callback_url is passed correctly
        from app.core.config import settings
        expected_callback = f"{settings.FRONTEND_URL}/payment/verify"
        mock_provider.initialize_transaction.assert_called_once()
        kwargs = mock_provider.initialize_transaction.call_args[1]
        self.assertEqual(kwargs["callback_url"], expected_callback)

        # Verify DB Purchase
        purchase = self.db.query(Purchase).first()
        self.assertIsNotNone(purchase)
        self.assertEqual(purchase.status, PurchaseStatus.PENDING)
        self.assertEqual(purchase.product_id, "credit_small")
        self.assertEqual(purchase.user_id, self.user.id)
        # Verify provider called with exact snapshot values
        mock_provider.initialize_transaction.assert_called_once_with(
            amount=1500,
            currency="NGN",
            email=self.user.email,
            reference=purchase.payment_reference,
            callback_url=expected_callback
        )

    def test_checkout_invalid_product(self):
        response = self.client.post("/api/payments/checkout", json={
            "product_id": "invalid_product"
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "Invalid or inactive product.")

    @patch("app.api.payments.PaystackProvider")
    def test_checkout_provider_error(self, mock_provider_class):
        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider
        mock_provider.initialize_transaction.side_effect = PaymentInitializationError("Provider down")

        response = self.client.post("/api/payments/checkout", json={
            "product_id": "credit_small"
        })
        self.assertEqual(response.status_code, 502)

    def test_checkout_unauthenticated(self):
        # Remove dependency override
        app.dependency_overrides.pop(get_current_user)
        
        response = self.client.post("/api/payments/checkout", json={
            "product_id": "credit_small"
        })
        self.assertEqual(response.status_code, 401)
