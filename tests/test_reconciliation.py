import unittest
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from app.db.database import Base
from app.models.wallet import Wallet
from app.models.ledger import LedgerTransaction, TransactionType
from app.models.user import User
from app.models.conversation import Conversation
from app.models.ai_request import AIRequestLog, RequestStatus, UsageSource
from app.services.credit_manager import reserve_credits
from app.services.reconciliation import reconcile_stale_requests

class TestReconciliation(unittest.TestCase):
    
    def setUp(self):
        from sqlalchemy.pool import StaticPool
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        Base.metadata.create_all(bind=self.engine)
        self.db = Session(bind=self.engine)
        
        self.user = User(first_name="Test", last_name="User", email="test@test.com", hashed_password="pw")
        self.db.add(self.user)
        self.db.commit()
        
        self.wallet = Wallet(user_id=self.user.id, subscription_balance=100, purchased_balance=50)
        self.db.add(self.wallet)
        
        self.conversation = Conversation(user_id=self.user.id, title="Test")
        self.db.add(self.conversation)
        self.db.commit()
        
        self.cutoff = datetime.now(timezone.utc)
        self.old_time = self.cutoff - timedelta(minutes=20)
        self.new_time = self.cutoff + timedelta(minutes=5)
        
    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        
    def _create_request(self, status=RequestStatus.PENDING, updated_at=None, req_id=1):
        req = AIRequestLog(
            id=req_id,
            user_id=self.user.id,
            conversation_id=self.conversation.id,
            client_request_id=f"req-{req_id}",
            provider="openai",
            model="gpt-4.1-mini",
            status=status
        )
        self.db.add(req)
        self.db.commit()
        return req
        
    def _set_updated_at(self, req_id, updated_at):
        req = self.db.query(AIRequestLog).get(req_id)
        req.updated_at = updated_at
        self.db.commit()

    def test_pending_no_reservation(self):
        req = self._create_request(req_id=1)
        self._set_updated_at(req.id, self.old_time)
        res = reconcile_stale_requests(self.db, self.cutoff)
        self.assertEqual(res["reconciled_count"], 1)
        self.db.refresh(req)
        self.assertEqual(req.status, RequestStatus.FAILED)
        txs = self.db.query(LedgerTransaction).all()
        self.assertEqual(len(txs), 0)

    def test_pending_reservation_no_usage(self):
        req = self._create_request(req_id=2)
        reserve_credits(self.db, self.user.id, request_id=req.id, max_cost=50)
        self._set_updated_at(req.id, self.old_time)
        
        self.db.refresh(self.wallet)
        self.assertEqual(self.wallet.reserved_balance, 50)
        
        res = reconcile_stale_requests(self.db, self.cutoff)
        self.assertEqual(res["released_count"], 1)
        
        self.db.refresh(req)
        self.assertEqual(req.status, RequestStatus.FAILED)
        
        self.db.refresh(self.wallet)
        self.assertEqual(self.wallet.reserved_balance, 0)
        
        txs = self.db.query(LedgerTransaction).filter_by(reference_id=str(req.id)).all()
        types = [tx.transaction_type for tx in txs]
        self.assertIn(TransactionType.RESERVATION_RELEASE, types)
        self.assertNotIn(TransactionType.CHARGE, types)

    def test_pending_reservation_provider_usage_overrun(self):
        req = self._create_request(req_id=3)
        req.prompt_tokens = 10
        req.usage_source = UsageSource.PROVIDER
        self.db.commit()
        
        reserve_credits(self.db, self.user.id, request_id=req.id, max_cost=50)
        self._set_updated_at(req.id, self.old_time)
        
        res = reconcile_stale_requests(self.db, self.cutoff)
        self.assertEqual(res["overrun_count"], 1)
        
        self.db.refresh(req)
        self.assertEqual(req.status, RequestStatus.PENDING) # Still PENDING
        
        self.db.refresh(self.wallet)
        self.assertEqual(self.wallet.reserved_balance, 50) # Not released
        
        txs = self.db.query(LedgerTransaction).filter_by(reference_id=str(req.id)).all()
        types = [tx.transaction_type for tx in txs]
        self.assertNotIn(TransactionType.RESERVATION_RELEASE, types)

    def test_pending_release_and_charge(self):
        req = self._create_request(req_id=4)
        
        # Simulate successful finalization that didn't update status to COMPLETED
        self.db.add(LedgerTransaction(wallet_id=self.wallet.id, amount=-50, transaction_type=TransactionType.RESERVATION, reference_id="4"))
        self.db.add(LedgerTransaction(wallet_id=self.wallet.id, amount=50, transaction_type=TransactionType.RESERVATION_RELEASE, reference_id="4"))
        self.db.add(LedgerTransaction(wallet_id=self.wallet.id, amount=-40, transaction_type=TransactionType.CHARGE, reference_id="4"))
        self.db.commit()
        self._set_updated_at(req.id, self.old_time)
        
        res = reconcile_stale_requests(self.db, self.cutoff)
        self.assertEqual(res["already_settled_count"], 1)
        
        self.db.refresh(req)
        self.assertEqual(req.status, RequestStatus.COMPLETED)
        
    def test_pending_release_no_charge(self):
        req = self._create_request(req_id=5)
        
        # Simulate 0-cost finalization
        self.db.add(LedgerTransaction(wallet_id=self.wallet.id, amount=-50, transaction_type=TransactionType.RESERVATION, reference_id="5"))
        self.db.add(LedgerTransaction(wallet_id=self.wallet.id, amount=50, transaction_type=TransactionType.RESERVATION_RELEASE, reference_id="5"))
        self.db.commit()
        self._set_updated_at(req.id, self.old_time)
        
        res = reconcile_stale_requests(self.db, self.cutoff)
        self.assertEqual(res["already_settled_count"], 1)
        
        self.db.refresh(req)
        self.assertEqual(req.status, RequestStatus.FAILED)
        
    def test_non_stale_pending(self):
        req = self._create_request(req_id=6)
        self._set_updated_at(req.id, self.new_time)
        res = reconcile_stale_requests(self.db, self.cutoff)
        self.assertEqual(res["inspected_count"], 0)
        
    def test_ignored_statuses(self):
        for stat, idx in [(RequestStatus.COMPLETED, 7), (RequestStatus.FAILED, 8), (RequestStatus.PARTIAL, 9)]:
            req = self._create_request(status=stat, req_id=idx)
            self._set_updated_at(req.id, self.old_time)
        res = reconcile_stale_requests(self.db, self.cutoff)
        self.assertEqual(res["inspected_count"], 0)

    def test_repeated_reconciliation(self):
        # Initial run for a crash scenario
        req = self._create_request(req_id=10)
        reserve_credits(self.db, self.user.id, request_id=req.id, max_cost=50)
        self._set_updated_at(req.id, self.old_time)
        
        res1 = reconcile_stale_requests(self.db, self.cutoff)
        self.assertEqual(res1["released_count"], 1)
        
        # Second run should ignore it because status is now FAILED
        res2 = reconcile_stale_requests(self.db, self.cutoff)
        self.assertEqual(res2["inspected_count"], 0)
        
        # What if status was somehow still PENDING but RELEASE exists?
        req.status = RequestStatus.PENDING
        self.db.commit()
        self._set_updated_at(req.id, self.old_time)
        
        res3 = reconcile_stale_requests(self.db, self.cutoff)
        self.assertEqual(res3["already_settled_count"], 1)
        self.assertEqual(res3["released_count"], 0)

if __name__ == '__main__':
    unittest.main()