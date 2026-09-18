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

if __name__ == "__main__":
    unittest.main()
