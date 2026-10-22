import unittest
import asyncio
from unittest.mock import patch, MagicMock

from app.models.ai_request import RequestStatus, UsageSource
from app.services.chat import process_chat_stream
from app.models.conversation import Conversation
from app.models.user import User

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.database import Base

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class TestProcessChatStream(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = TestingSessionLocal()
        
        self.user = User(first_name="T", last_name="U", email="test@ex.com", hashed_password="pw")
        self.db.add(self.user)
        self.db.commit()
        
        from app.models.wallet import Wallet
        self.wallet = Wallet(user_id=self.user.id, subscription_balance=1000)
        self.db.add(self.wallet)
        
        self.conv = Conversation(user_id=self.user.id, title="Test Conv")
        self.db.add(self.conv)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)

    @patch("app.services.chat.get_conversation_messages")
    @patch("app.services.chat.save_message")
    @patch("app.services.chat.structured_chat_stream")
    async def test_successful_completion(self, mock_stream, mock_save, mock_history):
        mock_history.return_value = []
        
        async def mock_generator():
            yield {"type": "content", "content": "Hello "}
            yield {"type": "content", "content": "world"}
            yield {"type": "usage", "provider_request_id": "req-1", "prompt_tokens": 10, "completion_tokens": 2}
        mock_stream.return_value = mock_generator()
        
        gen = await process_chat_stream(self.db, self.user.id, self.conv.id, "Hi", "client_req_1")
        
        output = [chunk async for chunk in gen]
        self.assertEqual(output, ["Hello ", "world"])
        
        # Check AIRequestLog status
        from app.models.ai_request import AIRequestLog
        log = self.db.query(AIRequestLog).filter_by(client_request_id="client_req_1").first()
        self.assertEqual(log.status, RequestStatus.COMPLETED)
        self.assertEqual(log.provider_request_id, "req-1")
        self.assertEqual(log.prompt_tokens, 10)
        self.assertEqual(log.usage_source, UsageSource.PROVIDER)

    @patch("app.services.chat.get_conversation_messages")
    @patch("app.services.chat.save_message")
    @patch("app.services.chat.structured_chat_stream")
    async def test_provider_failure_no_output(self, mock_stream, mock_save, mock_history):
        mock_history.return_value = []
        
        async def mock_generator():
            raise Exception("API Error")
            yield  # just to make it a generator
        mock_stream.return_value = mock_generator()
        
        gen = await process_chat_stream(self.db, self.user.id, self.conv.id, "Hi", "client_req_2")
        
        with self.assertRaises(Exception):
            async for chunk in gen:
                pass
                
        from app.models.ai_request import AIRequestLog
        log = self.db.query(AIRequestLog).filter_by(client_request_id="client_req_2").first()
        self.assertEqual(log.status, RequestStatus.FAILED)
        
    @patch("app.services.chat.get_conversation_messages")
    @patch("app.services.chat.save_message")
    @patch("app.services.chat.structured_chat_stream")
    async def test_client_disconnect_partial_output(self, mock_stream, mock_save, mock_history):
        mock_history.return_value = []
        
        async def mock_generator():
            yield {"type": "content", "content": "Partial "}
            # Simulate GeneratorExit raised when client disconnects
            raise GeneratorExit()
            
        mock_stream.return_value = mock_generator()
        
        gen = await process_chat_stream(self.db, self.user.id, self.conv.id, "Hi", "client_req_3")
        
        with self.assertRaises(GeneratorExit):
            async for chunk in gen:
                pass
                
        from app.models.ai_request import AIRequestLog
        log = self.db.query(AIRequestLog).filter_by(client_request_id="client_req_3").first()
        self.assertEqual(log.status, RequestStatus.PARTIAL)
        self.assertIsNone(log.provider_request_id)
        self.assertIsNone(log.usage_source)

    @patch("app.services.title_generator.dispatch_background_title")
    @patch("app.services.chat.structured_chat_stream")
    async def test_stream_db_backed_title_trigger_and_bounded_context(self, mock_stream, mock_title):
        from datetime import datetime, timedelta, timezone
        from app.models.message import Message
        from app.services.context_manager import ContextManager
        from app.services.prompt_builder import SYSTEM_PROMPT

        async def _gen1():
            yield {"type": "content", "content": "Stream reply 1"}
            yield {"type": "usage", "provider_request_id": "req-s1", "prompt_tokens": 20, "completion_tokens": 4}

        mock_stream.return_value = _gen1()

        # First message in conversation triggers title dispatch
        gen1 = await process_chat_stream(self.db, self.user.id, self.conv.id, "First stream msg", "stream_req_first")
        chunks1 = [c async for c in gen1]
        self.assertEqual(chunks1, ["Stream reply 1"])
        mock_title.assert_called_once_with(self.conv.id, "First stream msg")
        mock_title.reset_mock()

        # Seed messages so history overflows a tight budget
        base = datetime.now(timezone.utc) - timedelta(minutes=10)
        for idx in range(10):
            self.db.add(
                Message(
                    conversation_id=self.conv.id,
                    role="user" if idx % 2 == 0 else "assistant",
                    content=f"Stream history {idx} " + ("word " * 15),
                    created_at=base + timedelta(seconds=idx),
                )
            )
        self.db.commit()

        async def _gen2():
            yield {"type": "content", "content": "Stream reply 2"}
            yield {"type": "usage", "provider_request_id": "req-s2", "prompt_tokens": 30, "completion_tokens": 4}

        mock_stream.return_value = _gen2()

        with patch("app.core.config.settings.MAX_INPUT_TOKENS", 260):
            gen2 = await process_chat_stream(
                self.db, self.user.id, self.conv.id, "Second stream msg", "stream_req_bounded"
            )
            chunks2 = [c async for c in gen2]
            self.assertEqual(chunks2, ["Stream reply 2"])

        mock_title.assert_not_called()

        sent_contents = mock_stream.call_args[0][0]
        all_msgs = (
            self.db.query(Message)
            .filter(Message.conversation_id == self.conv.id)
            .order_by(Message.created_at.asc(), Message.id.asc())
            .all()
        )
        prior_before_reply = all_msgs[:-2]
        raw_prior = [{"role": m.role, "content": m.content} for m in prior_before_reply]
        expected_ctx = ContextManager(max_input_tokens=260).build_context(
            SYSTEM_PROMPT, raw_prior, "Second stream msg"
        )
        expected_contents = expected_ctx["bounded_history"] + [
            {"role": "user", "content": "Second stream msg"}
        ]
        self.assertEqual(sent_contents, expected_contents)
        self.assertLess(len(expected_ctx["bounded_history"]), len(raw_prior))

if __name__ == "__main__":
    unittest.main()
