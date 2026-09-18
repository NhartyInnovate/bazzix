import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from app.db.database import Base
from app.models.user import User
from app.models.conversation import Conversation
from app.models.wallet import Wallet
from app.models.ledger import LedgerTransaction, TransactionType
from app.models.ai_request import AIRequestLog, UsageSource, RequestStatus
from decimal import Decimal

# Setup an in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class TestCreditModels(unittest.TestCase):
    def setUp(self):
        # Create all tables in the in-memory database
        Base.metadata.create_all(bind=engine)
        self.db = TestingSessionLocal()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)

    def _create_user(self, email="test@example.com"):
        user = User(
            first_name="Test",
            last_name="User",
            email=email,
            hashed_password="hashed_password",
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def _create_conversation(self, user_id):
        conv = Conversation(title="Test Conv", user_id=user_id)
        self.db.add(conv)
        self.db.commit()
        self.db.refresh(conv)
        return conv

    def test_wallet_creation_and_derived_balance(self):
        user = self._create_user()
        
        wallet = Wallet(
            user_id=user.id,
            subscription_balance=1000,
            purchased_balance=500,
            reserved_balance=200
        )
        self.db.add(wallet)
        self.db.commit()
        self.db.refresh(wallet)
        
        self.assertEqual(wallet.user_id, user.id)
        self.assertEqual(wallet.subscription_balance, 1000)
        self.assertEqual(wallet.purchased_balance, 500)
        self.assertEqual(wallet.reserved_balance, 200)
        self.assertEqual(wallet.available_credits, 1300)

    def test_wallet_uniqueness(self):
        user = self._create_user()
        wallet1 = Wallet(user_id=user.id)
        self.db.add(wallet1)
        self.db.commit()
        
        wallet2 = Wallet(user_id=user.id)
        self.db.add(wallet2)
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()

    def test_ledger_transaction(self):
        user = self._create_user()
        wallet = Wallet(user_id=user.id)
        self.db.add(wallet)
        self.db.commit()
        self.db.refresh(wallet)
        
        txn = LedgerTransaction(
            wallet_id=wallet.id,
            amount=-100,
            transaction_type=TransactionType.CHARGE,
            reference_id="req_123"
        )
        self.db.add(txn)
        self.db.commit()
        self.db.refresh(txn)
        
        self.assertEqual(txn.wallet_id, wallet.id)
        self.assertEqual(txn.amount, -100)
        self.assertEqual(txn.transaction_type, TransactionType.CHARGE)
        self.assertEqual(txn.reference_id, "req_123")
        self.assertIsNotNone(txn.created_at)

    def test_ai_request_log(self):
        user = self._create_user()
        conv = self._create_conversation(user.id)
        
        req_log = AIRequestLog(
            client_request_id="client_uuid_1",
            user_id=user.id,
            conversation_id=conv.id,
            provider="openai",
            model="gpt-4.1-mini",
            status=RequestStatus.PENDING
        )
        self.db.add(req_log)
        self.db.commit()
        self.db.refresh(req_log)
        
        self.assertEqual(req_log.client_request_id, "client_uuid_1")
        self.assertEqual(req_log.user_id, user.id)
        self.assertEqual(req_log.conversation_id, conv.id)
        self.assertEqual(req_log.status, RequestStatus.PENDING)
        self.assertIsNone(req_log.provider_cost)
        self.assertIsNone(req_log.prompt_tokens)

    def test_ai_request_log_update_completion(self):
        user = self._create_user()
        conv = self._create_conversation(user.id)
        
        req_log = AIRequestLog(
            client_request_id="client_uuid_2",
            user_id=user.id,
            conversation_id=conv.id,
            provider="openai",
            model="gpt-4.1-mini",
            status=RequestStatus.COMPLETED,
            provider_request_id="chatcmpl-123",
            prompt_tokens=100,
            completion_tokens=50,
            usage_source=UsageSource.PROVIDER,
            provider_cost=Decimal("0.0015")
        )
        self.db.add(req_log)
        self.db.commit()
        self.db.refresh(req_log)
        
        self.assertEqual(req_log.prompt_tokens, 100)
        self.assertEqual(req_log.usage_source, UsageSource.PROVIDER)
        self.assertEqual(req_log.provider_cost, Decimal("0.0015"))

    def test_ai_request_log_uniqueness(self):
        user = self._create_user()
        conv = self._create_conversation(user.id)
        
        req1 = AIRequestLog(
            client_request_id="duplicate_uuid",
            user_id=user.id,
            conversation_id=conv.id,
            model="gpt-4.1-mini"
        )
        self.db.add(req1)
        self.db.commit()
        
        req2 = AIRequestLog(
            client_request_id="duplicate_uuid",
            user_id=user.id,
            conversation_id=conv.id,
            model="gpt-4.1-mini"
        )
        self.db.add(req2)
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()

if __name__ == '__main__':
    unittest.main()
