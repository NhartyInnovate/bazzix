
import unittest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.database import Base
from app.db.dependencies import get_db
from app.core.dependencies import get_current_user
from app.models.user import User, RoleType
from app.models.wallet import Wallet
from app.models.ledger import LedgerTransaction, TransactionType
from app.models.audit import AdminAuditLog

class TestAdminAPI(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = self.SessionLocal()

        self.normal_user = User(
            id=1, first_name="Normal", last_name="User", email="normal@test.com",
            hashed_password="pw", is_active=True, role=RoleType.USER
        )
        self.admin_user = User(
            id=2, first_name="Admin", last_name="User", email="admin@test.com",
            hashed_password="pw", is_active=True, role=RoleType.ADMIN
        )
        self.db.add(self.normal_user)
        self.db.add(self.admin_user)
        self.db.commit()

        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def _set_user(self, user):
        app.dependency_overrides[get_current_user] = lambda: user

    def test_unauthenticated_401(self):
        response = self.client.get("/admin/stats")
        self.assertEqual(response.status_code, 401)

    def test_normal_user_403(self):
        self._set_user(self.normal_user)
        response = self.client.get("/admin/stats")
        self.assertEqual(response.status_code, 403)

    def test_admin_access_200(self):
        self._set_user(self.admin_user)
        response = self.client.get("/admin/health")
        self.assertEqual(response.status_code, 200)

    def test_admin_stats_structure(self):
        self._set_user(self.admin_user)
        response = self.client.get("/admin/stats")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total_users"], 2)
        self.assertEqual(data["active_users"], 2)
        self.assertTrue("total_provider_cost" in data)

    def test_user_listing_pagination_and_search(self):
        self._set_user(self.admin_user)
        response = self.client.get("/admin/users?page=1&size=10&search=normal")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["users"][0]["email"], "normal@test.com")

    def test_credit_adjustment(self):
        self._set_user(self.admin_user)
        wallet = Wallet(user_id=self.normal_user.id, subscription_balance=0, purchased_balance=0, reserved_balance=0)
        self.db.add(wallet)
        self.db.commit()

        # Positive adjustment
        resp1 = self.client.post("/admin/users/1/credits/adjust", json={"amount": 100, "reason": "Bonus"})
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(resp1.json()["new_balance"], 100)

        # Check ledger
        tx = self.db.query(LedgerTransaction).first()
        self.assertEqual(tx.amount, 100)
        self.assertEqual(tx.transaction_type, TransactionType.ADJUSTMENT)
        self.assertEqual(tx.reference_id, "Bonus")

        # Check audit
        audit = self.db.query(AdminAuditLog).first()
        self.assertEqual(audit.action, "CREDIT_ADJUSTMENT")
        self.assertEqual(audit.details["amount"], 100)

        # Negative adjustment (Success)
        resp2 = self.client.post("/admin/users/1/credits/adjust", json={"amount": -50, "reason": "Correction"})
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.json()["new_balance"], 50)

        # Negative adjustment (Insufficient)
        resp3 = self.client.post("/admin/users/1/credits/adjust", json={"amount": -100, "reason": "Overage"})
        self.assertEqual(resp3.status_code, 400)

    def test_credit_adjustment_zero(self):
        self._set_user(self.admin_user)
        resp = self.client.post("/admin/users/1/credits/adjust", json={"amount": 0, "reason": "Zero"})
        self.assertEqual(resp.status_code, 400)

    def test_user_detail(self):
        self._set_user(self.admin_user)
        wallet = Wallet(user_id=self.normal_user.id, subscription_balance=10, purchased_balance=20, reserved_balance=0)
        self.db.add(wallet)
        self.db.commit()
        resp = self.client.get("/admin/users/1")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["email"], "normal@test.com")
        self.assertEqual(data["available_credits"], 30)

    def test_usage_pagination(self):
        self._set_user(self.admin_user)
        resp = self.client.get("/admin/users/1/usage")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["total"], 0)

    def test_purchases_pagination(self):
        self._set_user(self.admin_user)
        resp = self.client.get("/admin/users/1/purchases")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["total"], 0)

    def test_ledger_pagination(self):
        self._set_user(self.admin_user)
        resp = self.client.get("/admin/users/1/ledger")
        self.assertEqual(resp.status_code, 200)

    def test_audit_logs_filtering(self):
        self._set_user(self.admin_user)

        # Create second normal user
        user2 = User(id=3, first_name="User2", last_name="Two", email="two@test.com", hashed_password="pw", role=RoleType.USER)
        self.db.add(user2)

        # Create audit records
        log1 = AdminAuditLog(admin_user_id=2, target_user_id=1, action="CREDIT_ADJUSTMENT")
        log2 = AdminAuditLog(admin_user_id=2, target_user_id=1, action="OTHER_ACTION")
        log3 = AdminAuditLog(admin_user_id=2, target_user_id=3, action="CREDIT_ADJUSTMENT")

        self.db.add_all([log1, log2, log3])
        self.db.commit()

        # A. Existing global behavior
        resp_global = self.client.get("/admin/audit-logs")
        self.assertEqual(resp_global.status_code, 200)
        global_data = resp_global.json()["items"]
        self.assertTrue(len(global_data) >= 3)

        # B. Scoped behavior & C. Isolation
        resp_scoped = self.client.get("/admin/audit-logs?target_user_id=1")
        self.assertEqual(resp_scoped.status_code, 200)
        scoped_data = resp_scoped.json()["items"]
        self.assertEqual(len(scoped_data), 2)
        self.assertTrue(all(item["target_user_id"] == 1 for item in scoped_data))

        # D. Non-existent target
        resp_none = self.client.get("/admin/audit-logs?target_user_id=999")
        self.assertEqual(resp_none.status_code, 200)
        self.assertEqual(len(resp_none.json()["items"]), 0)

        # E. Existing action filtering works combined
        resp_combined = self.client.get("/admin/audit-logs?target_user_id=1&action=CREDIT_ADJUSTMENT")
        self.assertEqual(resp_combined.status_code, 200)
        combined_data = resp_combined.json()["items"]
        self.assertEqual(len(combined_data), 1)
        self.assertEqual(combined_data[0]["action"], "CREDIT_ADJUSTMENT")

    def test_credit_adjustment_atomicity(self):
        self._set_user(self.admin_user)
        wallet = Wallet(user_id=self.normal_user.id, subscription_balance=100, purchased_balance=0, reserved_balance=0)
        self.db.add(wallet)
        self.db.commit()

        # Force a failure during commit by temporarily overriding db.commit
        original_commit = self.db.commit
        def exploding_commit():
            raise Exception("Simulated Database Error")
        self.db.commit = exploding_commit

        resp = self.client.post("/admin/users/1/credits/adjust", json={"amount": 50, "reason": "Test Atomic"})
        self.assertEqual(resp.status_code, 500) # FastAPI turns unhandled exceptions into 500

        # Restore commit and rollback the failed transaction session
        self.db.commit = original_commit
        self.db.rollback()

        # Verify wallet unchanged
        wallet_after = self.db.query(Wallet).filter_by(user_id=1).first()
        self.assertEqual(wallet_after.available_credits, 100)
        
        # Verify no ledger
        tx_count = self.db.query(LedgerTransaction).count()
        self.assertEqual(tx_count, 0)
        
        # Verify no audit
        audit_count = self.db.query(AdminAuditLog).count()
        self.assertEqual(audit_count, 0)

