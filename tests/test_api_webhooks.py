import hmac
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.database import Base
from app.db.dependencies import get_db
from app.core.config import settings
from app.models.user import User
from app.models.wallet import Wallet
from app.models.ledger import LedgerTransaction
from app.models.purchase import Purchase, PurchaseStatus
from app.services.allocation import AllocationTransientError

class TestWebhooksAPI(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            'sqlite:///:memory:', 
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = self.SessionLocal()

        # Seed data
        self.user = User(
            id=1,
            first_name="Test",
            last_name="User",
            email="test@example.com",
            hashed_password="pw",
            is_active=True
        )
        self.db.add(self.user)
        self.wallet = Wallet(user_id=1, subscription_balance=0, purchased_balance=0, reserved_balance=0)
        self.db.add(self.wallet)
        
        self.purchase = Purchase(
            id=1,
            user_id=1,
            product_id="credit_small",
            product_name_snapshot="Small Pack",
            price_amount=1500,
            price_currency="NGN",
            credit_allocation=5000,
            payment_provider="paystack",
            payment_reference="bzx_123",
            status=PurchaseStatus.PENDING
        )
        self.db.add(self.purchase)
        self.db.commit()

        def override_get_db():
            yield self.db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

        # Ensure a predictable secret key for tests
        self.original_key = settings.PAYSTACK_SECRET_KEY
        settings.PAYSTACK_SECRET_KEY = "test_secret_key"

    def tearDown(self):
        settings.PAYSTACK_SECRET_KEY = self.original_key
        app.dependency_overrides.clear()
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def _generate_signature(self, payload_bytes: bytes) -> str:
        return hmac.new(
            "test_secret_key".encode('utf-8'),
            payload_bytes,
            digestmod='sha512'
        ).hexdigest()

    def test_missing_signature(self):
        response = self.client.post("/api/webhooks/paystack", content=b'{}')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["message"], "Missing signature")

    def test_invalid_signature(self):
        response = self.client.post(
            "/api/webhooks/paystack", 
            content=b'{}',
            headers={"x-paystack-signature": "invalidhex"}
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["message"], "Invalid signature")

    def test_malformed_json(self):
        body = b'not json'
        sig = self._generate_signature(body)
        response = self.client.post(
            "/api/webhooks/paystack",
            content=body,
            headers={"x-paystack-signature": sig}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "Malformed JSON")

    def test_unknown_event(self):
        payload = {"event": "transfer.success"}
        body = json.dumps(payload).encode('utf-8')
        sig = self._generate_signature(body)
        response = self.client.post(
            "/api/webhooks/paystack",
            content=body,
            headers={"x-paystack-signature": sig}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")

    def test_unknown_reference(self):
        payload = {
            "event": "charge.success",
            "data": {
                "reference": "unknown_123",
                "amount": 150000,
                "currency": "NGN",
                "id": 999
            }
        }
        body = json.dumps(payload).encode('utf-8')
        sig = self._generate_signature(body)
        response = self.client.post(
            "/api/webhooks/paystack",
            content=body,
            headers={"x-paystack-signature": sig}
        )
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["message"], "Purchase reference not found")

    def test_missing_required_data(self):
        payload = {
            "event": "charge.success",
            "data": {
                "reference": "bzx_123"
                # Missing amount, currency, id
            }
        }
        body = json.dumps(payload).encode('utf-8')
        sig = self._generate_signature(body)
        response = self.client.post(
            "/api/webhooks/paystack",
            content=body,
            headers={"x-paystack-signature": sig}
        )
        self.assertEqual(response.status_code, 400)

    def test_valid_fulfillment(self):
        payload = {
            "event": "charge.success",
            "data": {
                "reference": "bzx_123",
                "amount": 150000,  # 1500 NGN in kobo
                "currency": "NGN",
                "id": 9999,
                "paid_at": "2026-09-18T12:00:00.000Z"
            }
        }
        body = json.dumps(payload).encode('utf-8')
        sig = self._generate_signature(body)
        response = self.client.post(
            "/api/webhooks/paystack",
            content=body,
            headers={"x-paystack-signature": sig}
        )
        self.assertEqual(response.status_code, 200)

        # Check DB State in existing session
        self.db.refresh(self.purchase)
        self.assertEqual(self.purchase.status, PurchaseStatus.SUCCESS)
        self.assertEqual(self.purchase.provider_transaction_id, "9999")
        self.assertEqual(self.purchase.paid_at.year, 2026)

        self.db.refresh(self.wallet)
        self.assertEqual(self.wallet.purchased_balance, 5000)

        ledger_tx = self.db.query(LedgerTransaction).first()
        self.assertIsNotNone(ledger_tx)
        self.assertEqual(ledger_tx.amount, 5000)
        self.assertEqual(ledger_tx.reference_id, "purchase_1")

        # Verify DB changes survive closing the request session in a fresh session
        fresh_db = self.SessionLocal()
        fresh_purchase = fresh_db.query(Purchase).filter(Purchase.payment_reference == "bzx_123").first()
        self.assertEqual(fresh_purchase.status, PurchaseStatus.SUCCESS)
        self.assertEqual(fresh_purchase.provider_transaction_id, "9999")
        fresh_wallet = fresh_db.query(Wallet).filter(Wallet.user_id == self.user.id).first()
        self.assertEqual(fresh_wallet.purchased_balance, 5000)
        fresh_ledger = fresh_db.query(LedgerTransaction).filter(LedgerTransaction.wallet_id == fresh_wallet.id).first()
        self.assertIsNotNone(fresh_ledger)
        self.assertEqual(fresh_ledger.amount, 5000)
        self.assertEqual(fresh_ledger.reference_id, "purchase_1")
        fresh_db.close()

    def test_duplicate_webhook(self):
        # Already successful
        self.purchase.status = PurchaseStatus.SUCCESS
        self.db.commit()

        payload = {
            "event": "charge.success",
            "data": {
                "reference": "bzx_123",
                "amount": 150000,
                "currency": "NGN",
                "id": 9999
            }
        }
        body = json.dumps(payload).encode('utf-8')
        sig = self._generate_signature(body)
        response = self.client.post(
            "/api/webhooks/paystack",
            content=body,
            headers={"x-paystack-signature": sig}
        )
        self.assertEqual(response.status_code, 200)

        # Balance remains 0 (no duplicate credit)
        self.db.refresh(self.wallet)
        self.assertEqual(self.wallet.purchased_balance, 0)

        # Check in fresh session
        fresh_db = self.SessionLocal()
        fresh_wallet = fresh_db.query(Wallet).filter(Wallet.user_id == self.user.id).first()
        self.assertEqual(fresh_wallet.purchased_balance, 0)
        fresh_db.close()

    def test_amount_mismatch(self):
        payload = {
            "event": "charge.success",
            "data": {
                "reference": "bzx_123",
                "amount": 100000,  # 1000 NGN instead of 1500
                "currency": "NGN",
                "id": 9999
            }
        }
        body = json.dumps(payload).encode('utf-8')
        sig = self._generate_signature(body)
        response = self.client.post(
            "/api/webhooks/paystack",
            content=body,
            headers={"x-paystack-signature": sig}
        )
        # Returns 200 to ack Paystack, but does NOT fulfill
        self.assertEqual(response.status_code, 200)

        self.db.refresh(self.purchase)
        self.assertEqual(self.purchase.status, PurchaseStatus.PENDING)
        self.db.refresh(self.wallet)
        self.assertEqual(self.wallet.purchased_balance, 0)

    def test_currency_mismatch(self):
        payload = {
            "event": "charge.success",
            "data": {
                "reference": "bzx_123",
                "amount": 150000,
                "currency": "USD",  # USD instead of NGN
                "id": 9999
            }
        }
        body = json.dumps(payload).encode('utf-8')
        sig = self._generate_signature(body)
        response = self.client.post(
            "/api/webhooks/paystack",
            content=body,
            headers={"x-paystack-signature": sig}
        )
        # Returns 200 to ack Paystack, but does NOT fulfill
        self.assertEqual(response.status_code, 200)

        self.db.refresh(self.purchase)
        self.assertEqual(self.purchase.status, PurchaseStatus.PENDING)
        self.db.refresh(self.wallet)
        self.assertEqual(self.wallet.purchased_balance, 0)

    @patch("app.api.webhooks.fulfill_purchase")
    def test_database_failure(self, mock_fulfill):
        mock_fulfill.side_effect = Exception("DB Down")
        
        payload = {
            "event": "charge.success",
            "data": {
                "reference": "bzx_123",
                "amount": 150000,
                "currency": "NGN",
                "id": 9999
            }
        }
        body = json.dumps(payload).encode('utf-8')
        sig = self._generate_signature(body)
        response = self.client.post(
            "/api/webhooks/paystack",
            content=body,
            headers={"x-paystack-signature": sig}
        )
        self.assertEqual(response.status_code, 500)

    def test_fractional_amount(self):
        payload = {
            "event": "charge.success",
            "data": {
                "reference": "bzx_123",
                "amount": 250050,  # 2500.50 NGN in kobo
                "currency": "NGN",
                "id": 9999
            }
        }
        body = json.dumps(payload).encode('utf-8')
        sig = self._generate_signature(body)
        response = self.client.post(
            "/api/webhooks/paystack",
            content=body,
            headers={"x-paystack-signature": sig}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "Amount must represent whole currency units")

        self.db.refresh(self.purchase)
        self.assertEqual(self.purchase.status, PurchaseStatus.PENDING)
        self.db.refresh(self.wallet)
        self.assertEqual(self.wallet.purchased_balance, 0)

    def test_fulfillment_missing_wallet_auto_provisions(self):
        # Remove wallet to simulate missing wallet scenario
        self.db.delete(self.wallet)
        self.db.commit()

        payload = {
            "event": "charge.success",
            "data": {
                "reference": "bzx_123",
                "amount": 150000,
                "currency": "NGN",
                "id": 9999,
                "paid_at": "2026-03-30T10:00:00.000Z"
            }
        }
        body = json.dumps(payload).encode('utf-8')
        sig = self._generate_signature(body)
        response = self.client.post(
            "/api/webhooks/paystack",
            content=body,
            headers={"x-paystack-signature": sig}
        )
        self.assertEqual(response.status_code, 200)

        # Verify in fresh session that wallet was auto-provisioned and credited
        fresh_db = self.SessionLocal()
        fresh_purchase = fresh_db.query(Purchase).filter(Purchase.payment_reference == "bzx_123").first()
        self.assertEqual(fresh_purchase.status, PurchaseStatus.SUCCESS)
        fresh_wallet = fresh_db.query(Wallet).filter(Wallet.user_id == self.user.id).first()
        self.assertIsNotNone(fresh_wallet)
        self.assertEqual(fresh_wallet.purchased_balance, 5000)
        fresh_ledger = fresh_db.query(LedgerTransaction).filter(LedgerTransaction.wallet_id == fresh_wallet.id).first()
        self.assertIsNotNone(fresh_ledger)
        self.assertEqual(fresh_ledger.amount, 5000)
        fresh_db.close()

    def test_failed_purchase_recovery_via_webhook(self):
        # A verified charge.success for a purchase in FAILED status must be safely recovered and credited
        self.purchase.status = PurchaseStatus.FAILED
        self.db.commit()

        payload = {
            "event": "charge.success",
            "data": {
                "reference": "bzx_123",
                "amount": 150000,
                "currency": "NGN",
                "id": 9999,
                "paid_at": "2026-03-30T10:00:00.000Z"
            }
        }
        body = json.dumps(payload).encode('utf-8')
        sig = self._generate_signature(body)
        response = self.client.post(
            "/api/webhooks/paystack",
            content=body,
            headers={"x-paystack-signature": sig}
        )
        self.assertEqual(response.status_code, 200)

        # Verify in fresh session that purchase transitioned to SUCCESS and wallet was credited
        fresh_db = self.SessionLocal()
        fresh_purchase = fresh_db.query(Purchase).filter(Purchase.payment_reference == "bzx_123").first()
        self.assertEqual(fresh_purchase.status, PurchaseStatus.SUCCESS)
        self.assertEqual(fresh_purchase.provider_transaction_id, "9999")
        fresh_wallet = fresh_db.query(Wallet).filter(Wallet.user_id == self.user.id).first()
        self.assertEqual(fresh_wallet.purchased_balance, 5000)
        fresh_ledger = fresh_db.query(LedgerTransaction).filter(LedgerTransaction.wallet_id == fresh_wallet.id).first()
        self.assertIsNotNone(fresh_ledger)
        self.assertEqual(fresh_ledger.amount, 5000)
        fresh_db.close()

    def test_unknown_reference_returns_500(self):
        # A verified charge.success for an unknown reference must NEVER return 200 uncredited; it must return 500
        payload = {
            "event": "charge.success",
            "data": {
                "reference": "bzx_unknown_reference_999",
                "amount": 150000,
                "currency": "NGN",
                "id": 8888,
                "paid_at": "2026-03-30T10:00:00.000Z"
            }
        }
        body = json.dumps(payload).encode('utf-8')
        sig = self._generate_signature(body)
        response = self.client.post(
            "/api/webhooks/paystack",
            content=body,
            headers={"x-paystack-signature": sig}
        )
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["message"], "Purchase reference not found")

        # Verify wallet remains 0
        fresh_db = self.SessionLocal()
        fresh_wallet = fresh_db.query(Wallet).filter(Wallet.user_id == self.user.id).first()
        self.assertEqual(fresh_wallet.purchased_balance, 0)
        fresh_db.close()

    @patch("app.api.webhooks.fulfill_purchase")
    def test_recoverable_transient_failure_returns_500(self, mock_fulfill):
        mock_fulfill.side_effect = AllocationTransientError("Transient DB lock")

        payload = {
            "event": "charge.success",
            "data": {
                "reference": "bzx_123",
                "amount": 150000,
                "currency": "NGN",
                "id": 9999
            }
        }
        body = json.dumps(payload).encode('utf-8')
        sig = self._generate_signature(body)
        response = self.client.post(
            "/api/webhooks/paystack",
            content=body,
            headers={"x-paystack-signature": sig}
        )
        # Must return 500 so Paystack retries
        self.assertEqual(response.status_code, 500)
