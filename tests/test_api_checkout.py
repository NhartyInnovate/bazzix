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
from app.core.config import settings


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

        self.original_key = settings.PAYSTACK_SECRET_KEY
        settings.PAYSTACK_SECRET_KEY = "test_secret_key"

    def tearDown(self):
        settings.PAYSTACK_SECRET_KEY = self.original_key
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

        response = self.client.post("/payments/checkout", json={
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

        # Verify DB Purchase survives closing the request session in a fresh session
        fresh_db = self.SessionLocal()
        purchase = fresh_db.query(Purchase).first()
        self.assertIsNotNone(purchase)
        self.assertEqual(purchase.status, PurchaseStatus.PENDING)
        self.assertEqual(purchase.product_id, "credit_small")
        self.assertEqual(purchase.user_id, self.user.id)
        # Verify provider called with exact snapshot values
        mock_provider.initialize_transaction.assert_called_once_with(
            amount=100,
            currency="NGN",
            email=self.user.email,
            reference=purchase.payment_reference,
            callback_url=expected_callback
        )
        fresh_db.close()

    def test_checkout_invalid_product(self):
        response = self.client.post("/payments/checkout", json={
            "product_id": "invalid_product"
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "Invalid or inactive product.")

    @patch("app.api.payments.PaystackProvider")
    def test_checkout_provider_error(self, mock_provider_class):
        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider
        mock_provider.initialize_transaction.side_effect = PaymentInitializationError("Provider down")

        response = self.client.post("/payments/checkout", json={
            "product_id": "credit_small"
        })
        self.assertEqual(response.status_code, 400)

        # Verify purchase remains PENDING so it is recoverable if provider actually charged
        fresh_db = self.SessionLocal()
        purchase = fresh_db.query(Purchase).first()
        self.assertIsNotNone(purchase)
        self.assertEqual(purchase.status, PurchaseStatus.PENDING)
        fresh_db.close()

    def test_checkout_unauthenticated(self):
        # Remove dependency override
        app.dependency_overrides.pop(get_current_user)
        
        response = self.client.post("/payments/checkout", json={
            "product_id": "credit_small"
        })
        self.assertEqual(response.status_code, 401)

    @patch("app.api.payments.PaystackProvider")
    def test_checkout_ambiguous_provider_timeout_recoverable_via_webhook(self, mock_provider_class):
        # 1. Provider initialize_transaction times out / network error
        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider
        mock_provider.initialize_transaction.side_effect = PaymentInitializationError("Network error during initialization.")

        response = self.client.post("/payments/checkout", json={
            "product_id": "credit_small"
        })
        self.assertEqual(response.status_code, 400)

        # 2. Verify durable PENDING purchase exists in fresh session
        fresh_db = self.SessionLocal()
        purchase = fresh_db.query(Purchase).filter(Purchase.user_id == self.user.id).first()
        self.assertIsNotNone(purchase)
        self.assertEqual(purchase.status, PurchaseStatus.PENDING)
        saved_ref = purchase.payment_reference
        fresh_db.close()

        # 3. Provider actually accepted charge remotely and webhook arrives
        import hmac, json
        from app.core.config import settings
        payload = {
            "event": "charge.success",
            "data": {
                "reference": saved_ref,
                "amount": 10000,
                "currency": "NGN",
                "id": 7777,
                "paid_at": "2026-03-30T10:00:00.000Z"
            }
        }
        body = json.dumps(payload).encode('utf-8')
        sig = hmac.new(settings.PAYSTACK_SECRET_KEY.encode('utf-8'), body, digestmod='sha512').hexdigest()

        webhook_response = self.client.post(
            "/api/webhooks/paystack",
            content=body,
            headers={"x-paystack-signature": sig}
        )
        self.assertEqual(webhook_response.status_code, 200)

        # 4. Verify in fresh session that purchase is SUCCESS and wallet credited
        fresh_db2 = self.SessionLocal()
        recovered_purchase = fresh_db2.query(Purchase).filter(Purchase.payment_reference == saved_ref).first()
        self.assertEqual(recovered_purchase.status, PurchaseStatus.SUCCESS)
        fresh_wallet = fresh_db2.query(Wallet).filter(Wallet.user_id == self.user.id).first()
        self.assertEqual(fresh_wallet.purchased_balance, 5000)
        fresh_db2.close()

    @patch("app.api.payments.initialize_purchase")
    def test_checkout_db_failure(self, mock_init):
        mock_init.side_effect = Exception("DB Connection Lost")

        response = self.client.post("/payments/checkout", json={
            "product_id": "credit_small"
        })
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["message"], "Could not initialize purchase.")

        # Ensure no purchase is created in DB
        fresh_db = self.SessionLocal()
        purchases = fresh_db.query(Purchase).all()
        self.assertEqual(len(purchases), 0)
        fresh_db.close()
