import unittest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import uuid

from app.main import app
from app.db.database import Base
from app.db.dependencies import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.purchase import Purchase, PurchaseStatus
from app.models.wallet import Wallet

class TestPurchaseStatusAPI(unittest.TestCase):
    def setUp(self):
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

        self.other_user = User(
            id=2,
            first_name="Other",
            last_name="User",
            email="other@example.com",
            hashed_password="pw",
            is_active=True
        )
        self.db.add(self.other_user)
        self.db.commit()

        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        def override_get_current_user():
            return self.user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def _create_purchase(self, user_id, status=PurchaseStatus.PENDING):
        ref = f"bazzix_{uuid.uuid4()}"
        purchase = Purchase(
            user_id=user_id,
            product_id="credit_small",
            product_name_snapshot="Small Pack",
            credit_allocation=1000,
            price_amount=1000,
            price_currency="USD",
            payment_provider="paystack",
            payment_reference=ref,
            status=status
        )
        self.db.add(purchase)
        self.db.commit()
        return ref

    def test_status_pending(self):
        ref = self._create_purchase(self.user.id, PurchaseStatus.PENDING)
        response = self.client.get(f"/api/payments/{ref}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["reference"], ref)
        self.assertEqual(response.json()["status"], "PENDING")

    def test_status_success(self):
        ref = self._create_purchase(self.user.id, PurchaseStatus.SUCCESS)
        response = self.client.get(f"/api/payments/{ref}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "SUCCESS")

    def test_status_failed(self):
        ref = self._create_purchase(self.user.id, PurchaseStatus.FAILED)
        response = self.client.get(f"/api/payments/{ref}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "FAILED")

    def test_other_user_purchase_returns_404(self):
        ref = self._create_purchase(self.other_user.id)
        response = self.client.get(f"/api/payments/{ref}")
        self.assertEqual(response.status_code, 404)

    def test_unknown_reference_returns_404(self):
        response = self.client.get("/api/payments/bazzix_unknown")
        self.assertEqual(response.status_code, 404)

    def test_unauthenticated(self):
        ref = self._create_purchase(self.user.id)
        app.dependency_overrides.clear()
        response = self.client.get(f"/api/payments/{ref}")
        self.assertEqual(response.status_code, 401)
        
    def test_read_only_guarantee(self):
        ref = self._create_purchase(self.user.id, PurchaseStatus.PENDING)
        response = self.client.get(f"/api/payments/{ref}")
        self.assertEqual(response.status_code, 200)
        
        # Verify purchase unchanged
        purchase = self.db.query(Purchase).filter(Purchase.payment_reference == ref).first()
        self.assertEqual(purchase.status, PurchaseStatus.PENDING)
        
        # Verify no wallet created
        wallets = self.db.query(Wallet).all()
        self.assertEqual(len(wallets), 0)
