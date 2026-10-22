import unittest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.database import Base
from app.db.dependencies import get_db
from app.core.dependencies import get_current_user
from app.models.user import User, RoleType
from app.models.conversation import Conversation
from app.models.message import Message


class TestConversationSearchAPI(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = self.SessionLocal()

        now = datetime.now(timezone.utc)

        # Create two distinct users to verify strict isolation
        self.user1 = User(
            id=1,
            first_name="Alice",
            last_name="Tester",
            email="alice@test.com",
            hashed_password="pw",
            is_active=True,
            role=RoleType.USER,
        )
        self.user2 = User(
            id=2,
            first_name="Bob",
            last_name="Observer",
            email="bob@test.com",
            hashed_password="pw",
            is_active=True,
            role=RoleType.USER,
        )
        self.db.add_all([self.user1, self.user2])
        self.db.flush()

        # User 1 Conversations
        self.c1 = Conversation(
            id=101,
            title="Python Deployment Notes",
            is_pinned=True,
            user_id=self.user1.id,
            updated_at=now - timedelta(hours=2),
        )
        self.c2 = Conversation(
            id=102,
            title="General Workspace",
            is_pinned=False,
            user_id=self.user1.id,
            updated_at=now - timedelta(hours=1),
        )
        self.c3 = Conversation(
            id=103,
            title="Archive Chat",
            is_pinned=False,
            user_id=self.user1.id,
            updated_at=now - timedelta(days=2),
        )

        # User 2 Conversation (Private to user 2)
        self.c4_user2 = Conversation(
            id=201,
            title="Python Secret Strategy",
            is_pinned=False,
            user_id=self.user2.id,
            updated_at=now,
        )
        self.db.add_all([self.c1, self.c2, self.c3, self.c4_user2])
        self.db.flush()

        # User 1 Messages
        # c1 has a user message
        self.m1 = Message(
            id=1001,
            conversation_id=self.c1.id,
            role="user",
            content="How do we configure the Python virtual environment on Render?",
            created_at=now - timedelta(hours=2),
        )
        # c2 has an assistant message matching "Render" and multiple messages matching "database"
        self.m2 = Message(
            id=1002,
            conversation_id=self.c2.id,
            role="assistant",
            content="We should connect to PostgreSQL database on Render using Supabase session pooler on port 5432.",
            created_at=now - timedelta(hours=1, minutes=30),
        )
        self.m3 = Message(
            id=1003,
            conversation_id=self.c2.id,
            role="user",
            content="Can we run database migrations safely with Alembic?",
            created_at=now - timedelta(hours=1),
        )

        # User 2 Messages
        self.m4_user2 = Message(
            id=2001,
            conversation_id=self.c4_user2.id,
            role="user",
            content="Render configuration secret token for Bob.",
            created_at=now,
        )

        self.db.add_all([self.m1, self.m2, self.m3, self.m4_user2])
        self.db.commit()

        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        def override_current_user():
            return self.user1

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_current_user
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def test_search_requires_authentication(self):
        # Remove current_user override to test 401
        app.dependency_overrides.pop(get_current_user, None)
        res = self.client.get("/conversations/search?q=Python")
        self.assertEqual(res.status_code, 401)

    def test_search_user_isolation(self):
        # Bob's conversation c4_user2 has "Python Secret Strategy" and "Render configuration secret token"
        # Searching as Alice must NOT return Bob's conversation or messages
        res = self.client.get("/conversations/search?q=secret")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data), 0)

        # When searching "Python", Alice should see c1 ("Python Deployment Notes"), but NOT c4_user2
        res2 = self.client.get("/conversations/search?q=Python")
        self.assertEqual(res2.status_code, 200)
        ids = [item["id"] for item in res2.json()]
        self.assertIn(self.c1.id, ids)
        self.assertNotIn(self.c4_user2.id, ids)

    def test_search_matches_title(self):
        res = self.client.get("/conversations/search?q=Deployment")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], self.c1.id)
        self.assertEqual(data[0]["title"], "Python Deployment Notes")

    def test_search_matches_message_content(self):
        # "Supabase" is only in m2 inside conversation c2
        res = self.client.get("/conversations/search?q=Supabase")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], self.c2.id)
        self.assertEqual(data[0]["title"], "General Workspace")
        self.assertIsNotNone(data[0]["matching_snippet"])
        self.assertIn("Supabase", data[0]["matching_snippet"])

    def test_search_deduplicates_multiple_matching_messages(self):
        # Both m2 and m3 in conversation c2 contain "database"
        # The result must contain c2 exactly ONCE
        res = self.client.get("/conversations/search?q=database")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], self.c2.id)

    def test_search_empty_and_whitespace_query(self):
        res1 = self.client.get("/conversations/search?q=")
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1.json(), [])

        res2 = self.client.get("/conversations/search?q=   ")
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.json(), [])

    def test_search_respects_limit(self):
        # Limit to 1 result
        res = self.client.get("/conversations/search?q=Render&limit=1")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data), 1)

    def test_search_ordering_pinned_first(self):
        # Both c1 (pinned) and c2 (unpinned) match "Render"
        # c1 should appear first because is_pinned=True
        res = self.client.get("/conversations/search?q=Render")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["id"], self.c1.id)
        self.assertTrue(data[0]["is_pinned"])
        self.assertEqual(data[1]["id"], self.c2.id)
        self.assertFalse(data[1]["is_pinned"])

    def test_search_escapes_special_like_wildcards(self):
        # Querying % or _ should NOT act as full wildcards
        res = self.client.get("/conversations/search?q=%")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), [])

        res_underscore = self.client.get("/conversations/search?q=_")
        self.assertEqual(res_underscore.status_code, 200)
        self.assertEqual(res_underscore.json(), [])
