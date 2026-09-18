import unittest
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from app.db.database import Base
from app.models.wallet import Wallet
from app.models.ledger import LedgerTransaction, TransactionType
from app.models.user import User
from app.services.credit_manager import reserve_credits, InsufficientCreditsError, DuplicateReservationError
import threading

class TestCreditManager(unittest.TestCase):
    
    def setUp(self):
        # Use an in-memory SQLite for normal tests, but since we need to test
        # concurrency and row-level locks, SQLite is tricky. However, for unit testing 
        # basic functionality, it works. For strict row-lock concurrency, 
        # we'd need PostgreSQL. We will document the concurrency test limits.
        from sqlalchemy.pool import StaticPool
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        Base.metadata.create_all(bind=self.engine)
        self.db = Session(bind=self.engine)
        
        # Setup test data
        self.user = User(first_name="Test", last_name="User", email="test@test.com", hashed_password="pw")
        self.db.add(self.user)
        self.db.commit()
        
        self.wallet = Wallet(
            user_id=self.user.id,
            subscription_balance=100,
            purchased_balance=50,
            reserved_balance=0
        )
        self.db.add(self.wallet)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_successful_reservation(self):
        # User has 150 available. Reserve 80.
        reserve_credits(self.db, self.user.id, request_id=1, max_cost=80)
        
        self.db.refresh(self.wallet)
        self.assertEqual(self.wallet.reserved_balance, 80)
        self.assertEqual(self.wallet.available_credits, 70)
        
        # Check Ledger
        tx = self.db.query(LedgerTransaction).filter_by(reference_id="1").first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.amount, -80)
        self.assertEqual(tx.transaction_type, TransactionType.RESERVATION)

    def test_insufficient_credits(self):
        # User has 150 available. Try to reserve 200.
        with self.assertRaises(InsufficientCreditsError):
            reserve_credits(self.db, self.user.id, request_id=2, max_cost=200)
            
        self.db.refresh(self.wallet)
        self.assertEqual(self.wallet.reserved_balance, 0)
        self.assertEqual(self.wallet.available_credits, 150)

    def test_duplicate_reservation(self):
        reserve_credits(self.db, self.user.id, request_id=3, max_cost=50)
        
        # Attempting again with same request_id should fail
        with self.assertRaises(DuplicateReservationError):
            reserve_credits(self.db, self.user.id, request_id=3, max_cost=50)
            
        self.db.refresh(self.wallet)
        self.assertEqual(self.wallet.reserved_balance, 50)
        
        # Should only be one ledger entry
        txs = self.db.query(LedgerTransaction).filter_by(reference_id="3").all()
        self.assertEqual(len(txs), 1)

    def test_successful_finalization_with_charge(self):
        # 1. Reserve
        reserve_credits(self.db, self.user.id, request_id=1, max_cost=100)
        
        # 2. Finalize
        from app.services.credit_manager import finalize_and_settle_credits
        from app.models.ai_request import AIRequestLog, RequestStatus, UsageSource
        
        # Create a dummy AIRequestLog
        req = AIRequestLog(id=1, user_id=self.user.id, conversation_id=1, client_request_id="cli1", provider="openai", model="gpt-4.1-mini")
        
        # We need the pricing config to calculate the charge. 
        # Using configured provider: prompt 0.0000004, comp 0.0000016
        # Say 1000 prompt tokens, 1000 comp tokens. Cost is small.
        # It will hit the minimum charge of 10 credits.
        finalize_and_settle_credits(
            self.db, req, 
            status=RequestStatus.COMPLETED,
            prompt_tokens=1000,
            completion_tokens=1000,
            cached_tokens=0,
            usage_source=UsageSource.PROVIDER
        )
        
        self.db.refresh(self.wallet)
        # Reservation should be released
        self.assertEqual(self.wallet.reserved_balance, 0)
        
        # Check Ledger
        txs = self.db.query(LedgerTransaction).filter_by(reference_id="1").all()
        types = [tx.transaction_type for tx in txs]
        self.assertIn(TransactionType.RESERVATION, types)
        self.assertIn(TransactionType.RESERVATION_RELEASE, types)
        self.assertIn(TransactionType.CHARGE, types)
        
        charge_tx = next(tx for tx in txs if tx.transaction_type == TransactionType.CHARGE)
        self.assertTrue(charge_tx.amount < 0)
        
        # Subscription consumed first
        # Started with 100 subscription, 50 purchased
        self.assertTrue(self.wallet.subscription_balance < 100)
        self.assertTrue(self.wallet.purchased_balance <= 50)
        self.assertEqual(req.status, RequestStatus.COMPLETED)

    def test_missing_usage_no_charge(self):
        reserve_credits(self.db, self.user.id, request_id=2, max_cost=50)
        
        from app.services.credit_manager import finalize_and_settle_credits
        from app.models.ai_request import AIRequestLog, RequestStatus
        req = AIRequestLog(id=2, user_id=self.user.id, conversation_id=1, client_request_id="cli2", provider="openai", model="gpt-4.1-mini")
        
        # Finalize without usage (e.g. failure)
        finalize_and_settle_credits(self.db, req, status=RequestStatus.FAILED)
        
        self.db.refresh(self.wallet)
        self.assertEqual(self.wallet.reserved_balance, 0)
        self.assertEqual(self.wallet.subscription_balance, 100) # Unchanged
        
        txs = self.db.query(LedgerTransaction).filter_by(reference_id="2").all()
        types = [tx.transaction_type for tx in txs]
        self.assertIn(TransactionType.RESERVATION_RELEASE, types)
        self.assertNotIn(TransactionType.CHARGE, types)
        
    def test_duplicate_finalization(self):
        reserve_credits(self.db, self.user.id, request_id=3, max_cost=50)
        from app.services.credit_manager import finalize_and_settle_credits, DuplicateFinalizationError
        from app.models.ai_request import AIRequestLog, RequestStatus
        req = AIRequestLog(id=3, user_id=self.user.id, conversation_id=1, client_request_id="cli3", provider="openai", model="gpt-4.1-mini")
        
        finalize_and_settle_credits(self.db, req, status=RequestStatus.FAILED)
        
        with self.assertRaises(DuplicateFinalizationError):
            finalize_and_settle_credits(self.db, req, status=RequestStatus.FAILED)

    def test_subscription_and_purchased_consumption(self):
        # User has 100 sub, 50 purc
        reserve_credits(self.db, self.user.id, request_id=4, max_cost=150)
        
        from app.services.credit_manager import finalize_and_settle_credits
        from app.models.ai_request import AIRequestLog, RequestStatus
        req = AIRequestLog(id=4, user_id=self.user.id, conversation_id=1, client_request_id="cli4", provider="openai", model="gpt-4.1-mini")
        
        # We need exact cost to be 120 credits
        # 120 credits = $12 (with 10.0 exchange rate)
        # We will mock the `calculate_cost` directly for this test
        import unittest.mock as mock
        from app.services.pricing import PricingResult
        with mock.patch('app.services.pricing.calculate_cost') as mock_cost:
            mock_cost.return_value = PricingResult(provider_cost=12.0, bazzix_credits=120)
            
            finalize_and_settle_credits(
                self.db, req, status=RequestStatus.COMPLETED,
                prompt_tokens=10, completion_tokens=10
            )
            
        self.db.refresh(self.wallet)
        # 120 charge should consume 100 sub, leaving 0. Then 20 purc, leaving 30.
        self.assertEqual(self.wallet.subscription_balance, 0)
        self.assertEqual(self.wallet.purchased_balance, 30)
        self.assertEqual(self.wallet.reserved_balance, 0)

    def test_overrun_settlement_invariant_error(self):
        # User has 100 sub, 50 purc. Total 150 available.
        # Reserve 100.
        reserve_credits(self.db, self.user.id, request_id=5, max_cost=100)
        
        from app.services.credit_manager import finalize_and_settle_credits, SettlementInvariantError
        from app.models.ai_request import AIRequestLog, RequestStatus
        req = AIRequestLog(id=5, user_id=self.user.id, conversation_id=1, client_request_id="cli5", provider="openai", model="gpt-4.1-mini")
        
        # We need actual cost to exceed available credits (150). Let's mock cost to 200 credits.
        import unittest.mock as mock
        from app.services.pricing import PricingResult
        with mock.patch('app.services.pricing.calculate_cost') as mock_cost:
            mock_cost.return_value = PricingResult(provider_cost=20.0, bazzix_credits=200)
            
            with self.assertRaises(SettlementInvariantError):
                finalize_and_settle_credits(
                    self.db, req, status=RequestStatus.COMPLETED,
                    prompt_tokens=10, completion_tokens=10
                )
                
        self.db.refresh(self.wallet)
        # Reservation should NOT be released. Balances untouched.
        self.assertEqual(self.wallet.reserved_balance, 100)
        self.assertEqual(self.wallet.subscription_balance, 100)
        self.assertEqual(self.wallet.purchased_balance, 50)
        
        # Check Ledger: no CHARGE, no RESERVATION_RELEASE
        txs = self.db.query(LedgerTransaction).filter_by(reference_id="5").all()
        types = [tx.transaction_type for tx in txs]
        self.assertIn(TransactionType.RESERVATION, types)
        self.assertNotIn(TransactionType.RESERVATION_RELEASE, types)
        self.assertNotIn(TransactionType.CHARGE, types)
        
        # Check AIRequestLog was updated but kept its old status (PENDING)
        self.assertEqual(req.prompt_tokens, 10)
        self.assertEqual(req.completion_tokens, 10)
        self.assertEqual(req.status, RequestStatus.PENDING)


if __name__ == '__main__':
    unittest.main()
