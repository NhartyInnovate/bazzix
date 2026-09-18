import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.user import User
from app.models.conversation import Conversation
from app.services.ai_request import create_ai_request_log, finalize_ai_request_log, DuplicateRequestError
from app.models.ai_request import RequestStatus, UsageSource

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class TestAIRequestService(unittest.TestCase):
    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = TestingSessionLocal()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)

    def _create_user(self):
        user = User(first_name="T", last_name="U", email="test@ex.com", hashed_password="pw")
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def _create_conv(self, user_id):
        conv = Conversation(title="T", user_id=user_id)
        self.db.add(conv)
        self.db.commit()
        self.db.refresh(conv)
        return conv

    def test_create_ai_request_log(self):
        user = self._create_user()
        conv = self._create_conv(user.id)
        
        log = create_ai_request_log(self.db, "client_id_1", user.id, conv.id)
        self.assertEqual(log.status, RequestStatus.PENDING)
        self.assertIsNone(log.provider_request_id)
        self.assertIsNone(log.prompt_tokens)

    def test_duplicate_client_request_id(self):
        user = self._create_user()
        conv = self._create_conv(user.id)
        
        log = create_ai_request_log(self.db, "client_id_2", user.id, conv.id)
        
        with self.assertRaises(DuplicateRequestError) as context:
            create_ai_request_log(self.db, "client_id_2", user.id, conv.id)
            
        self.assertIn("(State: PENDING)", str(context.exception))
        
        # Now change state and check again
        log.status = RequestStatus.COMPLETED
        self.db.commit()
        
        with self.assertRaises(DuplicateRequestError) as context:
            create_ai_request_log(self.db, "client_id_2", user.id, conv.id)
            
        self.assertIn("(State: COMPLETED)", str(context.exception))
            
    def test_finalize_ai_request_log_success(self):
        user = self._create_user()
        conv = self._create_conv(user.id)
        
        log = create_ai_request_log(self.db, "client_id_3", user.id, conv.id)
        
        finalized = finalize_ai_request_log(
            self.db, 
            log, 
            provider_request_id="prov_123",
            prompt_tokens=10,
            cached_tokens=4,
            completion_tokens=20,
            usage_source=UsageSource.PROVIDER,
            status=RequestStatus.COMPLETED
        )
        
        self.assertEqual(finalized.status, RequestStatus.COMPLETED)
        self.assertEqual(finalized.provider_request_id, "prov_123")
        self.assertEqual(finalized.prompt_tokens, 10)
        self.assertEqual(finalized.cached_tokens, 4)
        self.assertEqual(finalized.completion_tokens, 20)
        self.assertEqual(finalized.usage_source, UsageSource.PROVIDER)
        
    def test_nullable_cached_tokens(self):
        user = self._create_user()
        conv = self._create_conv(user.id)
        
        log = create_ai_request_log(self.db, "client_id_4", user.id, conv.id)
        
        finalized = finalize_ai_request_log(
            self.db, 
            log, 
            provider_request_id="prov_456",
            prompt_tokens=15,
            # No cached_tokens passed
            completion_tokens=30,
            usage_source=UsageSource.PROVIDER,
            status=RequestStatus.COMPLETED
        )
        
        self.assertEqual(finalized.prompt_tokens, 15)
        self.assertIsNone(finalized.cached_tokens)
        self.assertEqual(finalized.completion_tokens, 30)

if __name__ == '__main__':
    unittest.main()
