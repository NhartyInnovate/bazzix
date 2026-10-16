import unittest
import asyncio
from unittest.mock import patch

from app.models.ai_request import RequestStatus, UsageSource, AIRequestLog
from app.services.chat import process_chat
from app.models.conversation import Conversation
from app.models.user import User
from app.models.wallet import Wallet
from app.models.ledger import LedgerTransaction, TransactionType
from app.services.credit_manager import InsufficientCreditsError
from app.services.ai_request import DuplicateRequestError

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.database import Base

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class TestProcessChat(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = TestingSessionLocal()

        self.user = User(first_name="Test", last_name="User", email="test_chat@example.com", hashed_password="pw")
        self.db.add(self.user)
        self.db.commit()

        self.wallet = Wallet(user_id=self.user.id, subscription_balance=1000, purchased_balance=500)
        self.db.add(self.wallet)

        self.conv = Conversation(user_id=self.user.id, title="Test Chat Conv")
        self.db.add(self.conv)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)

    @patch("app.services.chat.get_conversation_messages")
    @patch("app.services.chat.save_message")
    @patch("app.services.chat.structured_chat")
    async def test_process_chat_success(self, mock_chat, mock_save, mock_history):
        mock_history.return_value = []
        mock_chat.return_value = (
            "This is the synchronous AI response.",
            {
                "provider_request_id": "req-sync-1",
                "prompt_tokens": 20,
                "completion_tokens": 10,
                "cached_tokens": 0,
            }
        )

        initial_available = self.wallet.available_credits
        client_req_id = "test_sync_client_req_1"

        response = await process_chat(
            db=self.db,
            user_id=self.user.id,
            conversation_id=self.conv.id,
            user_message="Hello AI",
            client_request_id=client_req_id,
        )

        self.assertEqual(response, "This is the synchronous AI response.")

        # Check AIRequestLog
        log = self.db.query(AIRequestLog).filter_by(client_request_id=client_req_id).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.status, RequestStatus.COMPLETED)
        self.assertEqual(log.provider_request_id, "req-sync-1")
        self.assertEqual(log.prompt_tokens, 20)
        self.assertEqual(log.completion_tokens, 10)
        self.assertEqual(log.usage_source, UsageSource.PROVIDER)

        # Check that reservation was released and credits were settled/charged
        self.db.refresh(self.wallet)
        self.assertEqual(self.wallet.reserved_balance, 0)
        self.assertLess(self.wallet.available_credits, initial_available)

        # Check ledger entries: should have RESERVATION, RESERVATION_RELEASE, and CHARGE
        transactions = self.db.query(LedgerTransaction).filter_by(reference_id=str(log.id)).all()
        tx_types = [t.transaction_type for t in transactions]
        self.assertIn(TransactionType.RESERVATION, tx_types)
        self.assertIn(TransactionType.RESERVATION_RELEASE, tx_types)
        self.assertIn(TransactionType.CHARGE, tx_types)

    @patch("app.services.chat.get_conversation_messages")
    @patch("app.services.chat.save_message")
    async def test_process_chat_insufficient_credits(self, mock_save, mock_history):
        mock_history.return_value = []

        # Empty the wallet balances
        self.wallet.subscription_balance = 0
        self.wallet.purchased_balance = 0
        self.wallet.reserved_balance = 0
        self.db.commit()

        client_req_id = "test_sync_client_req_no_credits"

        with self.assertRaises(InsufficientCreditsError):
            await process_chat(
                db=self.db,
                user_id=self.user.id,
                conversation_id=self.conv.id,
                user_message="Hello without credits",
                client_request_id=client_req_id,
            )

        # AIRequestLog must be marked FAILED so it does not linger as PENDING
        log = self.db.query(AIRequestLog).filter_by(client_request_id=client_req_id).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.status, RequestStatus.FAILED)

        # Wallet balances should remain zero, no reserved credits
        self.db.refresh(self.wallet)
        self.assertEqual(self.wallet.reserved_balance, 0)
        self.assertEqual(self.wallet.available_credits, 0)

    @patch("app.services.chat.get_conversation_messages")
    @patch("app.services.chat.save_message")
    async def test_process_chat_duplicate_request_id(self, mock_save, mock_history):
        mock_history.return_value = []

        client_req_id = "test_sync_client_req_duplicate"
        # Pre-create AIRequestLog
        existing_log = AIRequestLog(
            client_request_id=client_req_id,
            user_id=self.user.id,
            conversation_id=self.conv.id,
            model="gpt-4.1-mini",
        )
        self.db.add(existing_log)
        self.db.commit()

        with self.assertRaises(DuplicateRequestError):
            await process_chat(
                db=self.db,
                user_id=self.user.id,
                conversation_id=self.conv.id,
                user_message="Duplicate message",
                client_request_id=client_req_id,
            )

    @patch("app.services.chat.get_conversation_messages")
    @patch("app.services.chat.save_message")
    @patch("app.services.chat.structured_chat")
    async def test_process_chat_provider_failure_releases_credits(self, mock_chat, mock_save, mock_history):
        mock_history.return_value = []
        mock_chat.side_effect = RuntimeError("OpenAI API Error: 500 Service Unavailable")

        initial_available = self.wallet.available_credits
        client_req_id = "test_sync_client_req_provider_failure"

        with self.assertRaises(RuntimeError):
            await process_chat(
                db=self.db,
                user_id=self.user.id,
                conversation_id=self.conv.id,
                user_message="Failing request",
                client_request_id=client_req_id,
            )

        # Check AIRequestLog: must be FAILED
        log = self.db.query(AIRequestLog).filter_by(client_request_id=client_req_id).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.status, RequestStatus.FAILED)

        # Wallet: reserved balance must be reset to 0, available credits restored
        self.db.refresh(self.wallet)
        self.assertEqual(self.wallet.reserved_balance, 0)
        self.assertEqual(self.wallet.available_credits, initial_available)

        # Ledger: must have RESERVATION and RESERVATION_RELEASE, but NO CHARGE
        transactions = self.db.query(LedgerTransaction).filter_by(reference_id=str(log.id)).all()
        tx_types = [t.transaction_type for t in transactions]
        self.assertIn(TransactionType.RESERVATION, tx_types)
        self.assertIn(TransactionType.RESERVATION_RELEASE, tx_types)
        self.assertNotIn(TransactionType.CHARGE, tx_types)

    async def test_process_chat_conversation_not_found(self):
        with self.assertRaises(ValueError) as ctx:
            await process_chat(
                db=self.db,
                user_id=self.user.id,
                conversation_id=999999,
                user_message="Hello",
            )
        self.assertIn("Conversation not found", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
