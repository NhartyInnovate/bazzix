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
from app.crud.message import encode_cursor, decode_cursor


class TestConversationsAPI(unittest.TestCase):
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
        self.user_empty = User(
            id=3,
            first_name="Empty",
            last_name="User",
            email="empty@test.com",
            hashed_password="pw",
            is_active=True,
            role=RoleType.USER,
        )
        self.db.add_all([self.user1, self.user2, self.user_empty])
        self.db.flush()

        # User 1 Conversations:
        # c1: Unpinned, recent
        self.c1 = Conversation(
            id=101,
            title="Alice Recent Chat",
            is_pinned=False,
            user_id=self.user1.id,
            created_at=now - timedelta(hours=2),
            updated_at=now - timedelta(hours=1),
        )
        # c2: Pinned, older
        self.c2 = Conversation(
            id=102,
            title="Alice Pinned Important",
            is_pinned=True,
            user_id=self.user1.id,
            created_at=now - timedelta(days=5),
            updated_at=now - timedelta(days=2),
        )
        # c3 and c4 have identical updated_at to test deterministic tie-breaking by id.desc()
        same_time = now - timedelta(days=1)
        self.c3_lower_id = Conversation(
            id=103,
            title="Tie Breaker Lower ID",
            is_pinned=False,
            user_id=self.user1.id,
            created_at=same_time,
            updated_at=same_time,
        )
        self.c4_higher_id = Conversation(
            id=104,
            title="Tie Breaker Higher ID",
            is_pinned=False,
            user_id=self.user1.id,
            created_at=same_time,
            updated_at=same_time,
        )
        # Empty conversation (no messages)
        self.c5_empty = Conversation(
            id=105,
            title="Alice Empty Chat",
            is_pinned=False,
            user_id=self.user1.id,
            created_at=now,
            updated_at=now,
        )

        # User 2 Conversation (Private to user 2)
        self.c_user2 = Conversation(
            id=201,
            title="Bob Secret Workspace",
            is_pinned=True,
            user_id=self.user2.id,
            created_at=now,
            updated_at=now,
        )

        self.db.add_all([self.c1, self.c2, self.c3_lower_id, self.c4_higher_id, self.c5_empty, self.c_user2])
        self.db.flush()

        # Messages for c1 in chronological order with one pair sharing identical timestamp
        msg_time = now - timedelta(hours=1)
        self.m1 = Message(
            id=1001,
            conversation_id=self.c1.id,
            role="user",
            content="First message in thread",
            created_at=msg_time - timedelta(minutes=10),
        )
        self.m2 = Message(
            id=1002,
            conversation_id=self.c1.id,
            role="assistant",
            content="Second message reply",
            created_at=msg_time - timedelta(minutes=5),
        )
        # Identical created_at for tie-breaking: lower ID vs higher ID
        tied_time = msg_time
        self.m3_lower_id = Message(
            id=1003,
            conversation_id=self.c1.id,
            role="user",
            content="Tied time third message lower id",
            created_at=tied_time,
        )
        self.m4_higher_id = Message(
            id=1004,
            conversation_id=self.c1.id,
            role="assistant",
            content="Tied time fourth message higher id",
            created_at=tied_time,
        )

        # Message belonging to Bob's conversation
        self.m_user2 = Message(
            id=2001,
            conversation_id=self.c_user2.id,
            role="user",
            content="Bob confidential message",
            created_at=now,
        )

        self.db.add_all([self.m1, self.m2, self.m3_lower_id, self.m4_higher_id, self.m_user2])
        self.db.commit()

        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        self.current_test_user = self.user1

        def override_current_user():
            return self.current_test_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_current_user
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def test_list_conversations_requires_auth(self):
        app.dependency_overrides.pop(get_current_user, None)
        res = self.client.get("/conversations")
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json().get("message"), "Not authenticated")

    def test_list_conversations_user_isolation(self):
        # Alice requests her conversations
        res = self.client.get("/conversations")
        self.assertEqual(res.status_code, 200)
        items = res.json()
        ids = [c["id"] for c in items]

        # Must include Alice's conversations
        self.assertIn(self.c1.id, ids)
        self.assertIn(self.c2.id, ids)
        # Must NEVER include Bob's conversation
        self.assertNotIn(self.c_user2.id, ids)

    def test_list_conversations_empty(self):
        # User with no conversations
        self.current_test_user = self.user_empty
        res = self.client.get("/conversations")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), [])

    def test_list_conversations_pinned_ordering(self):
        res = self.client.get("/conversations")
        self.assertEqual(res.status_code, 200)
        items = res.json()

        # The first item must be the pinned conversation (c2), despite having an older updated_at than c1
        self.assertTrue(items[0]["is_pinned"])
        self.assertEqual(items[0]["id"], self.c2.id)

    def test_list_conversations_deterministic_tie_breaker(self):
        # c3_lower_id (id: 103) and c4_higher_id (id: 104) share identical updated_at and are unpinned
        res = self.client.get("/conversations")
        self.assertEqual(res.status_code, 200)
        items = res.json()

        # Find indexes of c3 and c4
        idx_c3 = next(i for i, c in enumerate(items) if c["id"] == self.c3_lower_id.id)
        idx_c4 = next(i for i, c in enumerate(items) if c["id"] == self.c4_higher_id.id)

        # Higher ID must precede Lower ID deterministically when updated_at matches
        self.assertLess(idx_c4, idx_c3)

    def test_get_conversation_messages_chronological(self):
        res = self.client.get(f"/conversations/{self.c1.id}/messages")
        self.assertEqual(res.status_code, 200)
        messages = res.json()
        self.assertEqual(len(messages), 4)

        # Verify chronological sequence: m1 then m2
        self.assertEqual(messages[0]["id"], self.m1.id)
        self.assertEqual(messages[1]["id"], self.m2.id)

    def test_get_conversation_messages_stable_tie_breaker(self):
        # m3 (id: 1003) and m4 (id: 1004) share identical created_at
        res = self.client.get(f"/conversations/{self.c1.id}/messages")
        self.assertEqual(res.status_code, 200)
        messages = res.json()

        # Deterministic secondary order by id.asc()
        self.assertEqual(messages[2]["id"], self.m3_lower_id.id)
        self.assertEqual(messages[3]["id"], self.m4_higher_id.id)

    def test_get_conversation_messages_empty(self):
        # Empty conversation returns empty array
        res = self.client.get(f"/conversations/{self.c5_empty.id}/messages")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), [])

    def test_get_conversation_access_denied_for_other_user(self):
        # Alice attempting to get Bob's conversation must receive 403 Access denied
        res = self.client.get(f"/conversations/{self.c_user2.id}")
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json().get("message"), "Access denied")

    def test_get_conversation_messages_access_denied_for_other_user(self):
        # Alice attempting to read Bob's conversation messages must receive 403 Access denied
        res = self.client.get(f"/conversations/{self.c_user2.id}/messages")
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json().get("message"), "Access denied")

    def test_get_nonexistent_conversation_returns_404(self):
        res = self.client.get("/conversations/999999")
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json().get("message"), "Conversation not found")

    def test_get_nonexistent_conversation_messages_returns_404(self):
        res = self.client.get("/conversations/999999/messages")
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json().get("message"), "Conversation not found")

    def test_existing_search_endpoint_still_isolated(self):
        # Search query for "confidential" (present only in Bob's message) must return 0 items for Alice
        res = self.client.get("/conversations/search?q=confidential")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), [])

        # Search query for "message" should return c1 for Alice
        res_alice = self.client.get("/conversations/search?q=message")
        self.assertEqual(res_alice.status_code, 200)
        ids = [item["id"] for item in res_alice.json()]
        self.assertIn(self.c1.id, ids)
        self.assertNotIn(self.c_user2.id, ids)

    def test_get_conversation_messages_pagination_limit_only(self):
        # Alice requests latest 2 messages out of 4
        res = self.client.get(f"/conversations/{self.c1.id}/messages?limit=2")
        self.assertEqual(res.status_code, 200)
        messages = res.json()
        self.assertEqual(len(messages), 2)

        # Must be the latest 2 in chronological order: m3 then m4
        self.assertEqual(messages[0]["id"], self.m3_lower_id.id)
        self.assertEqual(messages[1]["id"], self.m4_higher_id.id)

        # Headers indicate more older messages exist and provide next cursor
        self.assertEqual(res.headers.get("x-has-more"), "true")
        self.assertIsNotNone(res.headers.get("x-next-cursor"))

    def test_get_conversation_messages_pagination_full_paging_via_cursor(self):
        # Page 1: latest 2 messages
        res1 = self.client.get(f"/conversations/{self.c1.id}/messages?limit=2")
        self.assertEqual(res1.status_code, 200)
        p1_messages = res1.json()
        self.assertEqual(len(p1_messages), 2)
        self.assertEqual(res1.headers.get("x-has-more"), "true")
        cursor = res1.headers.get("x-next-cursor")
        self.assertTrue(cursor)

        # Page 2: next 2 older messages using cursor
        res2 = self.client.get(f"/conversations/{self.c1.id}/messages?limit=2&cursor={cursor}")
        self.assertEqual(res2.status_code, 200)
        p2_messages = res2.json()
        self.assertEqual(len(p2_messages), 2)
        self.assertEqual(p2_messages[0]["id"], self.m1.id)
        self.assertEqual(p2_messages[1]["id"], self.m2.id)

        # No more older messages
        self.assertEqual(res2.headers.get("x-has-more"), "false")
        self.assertIsNone(res2.headers.get("x-next-cursor"))

        # Reconstructed full history must match chronological order
        full_ids = [m["id"] for m in (p2_messages + p1_messages)]
        self.assertEqual(full_ids, [self.m1.id, self.m2.id, self.m3_lower_id.id, self.m4_higher_id.id])

    def test_get_conversation_messages_pagination_via_before_id(self):
        # Alice requests messages before m3 (id 1003)
        res = self.client.get(f"/conversations/{self.c1.id}/messages?limit=2&before_id={self.m3_lower_id.id}")
        self.assertEqual(res.status_code, 200)
        messages = res.json()
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["id"], self.m1.id)
        self.assertEqual(messages[1]["id"], self.m2.id)
        self.assertEqual(res.headers.get("x-has-more"), "false")

    def test_get_conversation_messages_pagination_identical_timestamps_boundary(self):
        # Create a dedicated conversation with 5 messages, 3 of which share the identical timestamp
        conv = Conversation(
            id=301,
            title="Boundary Test Chat",
            is_pinned=False,
            user_id=self.user1.id,
        )
        self.db.add(conv)
        self.db.flush()

        base_time = datetime.now(timezone.utc) - timedelta(hours=3)
        shared_time = base_time + timedelta(minutes=5)

        # m_b0 (earlier), m_b1, m_b2, m_b3 (shared_time), m_b4 (later)
        msgs = [
            Message(id=3000, conversation_id=conv.id, role="user", content="msg 0", created_at=base_time),
            Message(id=3001, conversation_id=conv.id, role="assistant", content="msg 1", created_at=shared_time),
            Message(id=3002, conversation_id=conv.id, role="user", content="msg 2", created_at=shared_time),
            Message(id=3003, conversation_id=conv.id, role="assistant", content="msg 3", created_at=shared_time),
            Message(id=3004, conversation_id=conv.id, role="user", content="msg 4", created_at=base_time + timedelta(minutes=10)),
        ]
        self.db.add_all(msgs)
        self.db.commit()

        # Page 1: limit 2
        res1 = self.client.get(f"/conversations/{conv.id}/messages?limit=2")
        self.assertEqual(res1.status_code, 200)
        p1 = res1.json()
        self.assertEqual([m["id"] for m in p1], [3003, 3004])
        self.assertEqual(res1.headers.get("x-has-more"), "true")
        c1 = res1.headers.get("x-next-cursor")

        # Page 2: limit 2 with cursor (boundary inside shared_time messages)
        res2 = self.client.get(f"/conversations/{conv.id}/messages?limit=2&cursor={c1}")
        self.assertEqual(res2.status_code, 200)
        p2 = res2.json()
        self.assertEqual([m["id"] for m in p2], [3001, 3002])
        self.assertEqual(res2.headers.get("x-has-more"), "true")
        c2 = res2.headers.get("x-next-cursor")

        # Page 3: limit 2 with cursor
        res3 = self.client.get(f"/conversations/{conv.id}/messages?limit=2&cursor={c2}")
        self.assertEqual(res3.status_code, 200)
        p3 = res3.json()
        self.assertEqual([m["id"] for m in p3], [3000])
        self.assertEqual(res3.headers.get("x-has-more"), "false")

        # Reconstructed full history must contain all 5 messages exactly once in order
        all_ids = [m["id"] for m in (p3 + p2 + p1)]
        self.assertEqual(all_ids, [3000, 3001, 3002, 3003, 3004])

    def test_get_conversation_messages_pagination_fewer_than_limit(self):
        res = self.client.get(f"/conversations/{self.c1.id}/messages?limit=10")
        self.assertEqual(res.status_code, 200)
        messages = res.json()
        self.assertEqual(len(messages), 4)
        self.assertEqual(res.headers.get("x-has-more"), "false")
        self.assertIsNone(res.headers.get("x-next-cursor"))

    def test_get_conversation_messages_pagination_empty(self):
        res = self.client.get(f"/conversations/{self.c5_empty.id}/messages?limit=10")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), [])
        self.assertEqual(res.headers.get("x-has-more"), "false")
        self.assertIsNone(res.headers.get("x-next-cursor"))

    def test_get_conversation_messages_pagination_invalid_cursor(self):
        res = self.client.get(f"/conversations/{self.c1.id}/messages?limit=10&cursor=invalid_base64_cursor!!")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json().get("message"), "Invalid pagination cursor")

    def test_get_conversation_messages_pagination_invalid_before_id(self):
        res = self.client.get(f"/conversations/{self.c1.id}/messages?limit=10&before_id=999999")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json().get("message"), "Message anchor not found")

    def test_get_conversation_messages_pagination_invalid_limit(self):
        res_zero = self.client.get(f"/conversations/{self.c1.id}/messages?limit=0")
        self.assertEqual(res_zero.status_code, 422)

        res_over = self.client.get(f"/conversations/{self.c1.id}/messages?limit=101")
        self.assertEqual(res_over.status_code, 422)

    def test_get_conversation_messages_pagination_cross_user_before_id(self):
        # Alice attempts to use Bob's message (m_user2: 2001) as anchor for her conversation
        res = self.client.get(f"/conversations/{self.c1.id}/messages?limit=2&before_id={self.m_user2.id}")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json().get("message"), "Message anchor not found")

    def test_get_conversation_messages_pagination_user_isolation(self):
        # Alice attempts to paginate Bob's conversation
        res = self.client.get(f"/conversations/{self.c_user2.id}/messages?limit=10")
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json().get("message"), "Access denied")


class TestCursorEncoding(unittest.TestCase):
    def test_encode_and_decode_round_trip_utc(self):
        dt = datetime(2026, 10, 22, 12, 30, 45, 123456, tzinfo=timezone.utc)
        msg_id = 4294967
        cursor = encode_cursor(dt, msg_id)
        self.assertIsInstance(cursor, str)
        self.assertNotIn("=", cursor)  # Stripped padding

        decoded_dt, decoded_id = decode_cursor(cursor)
        self.assertEqual(decoded_dt, dt)
        self.assertEqual(decoded_id, msg_id)

    def test_encode_and_decode_round_trip_naive(self):
        dt = datetime(2026, 10, 22, 12, 30, 45, 0)
        msg_id = 101
        cursor = encode_cursor(dt, msg_id)

        decoded_dt, decoded_id = decode_cursor(cursor)
        self.assertEqual(decoded_dt, dt)
        self.assertEqual(decoded_id, msg_id)

    def test_decode_invalid_inputs(self):
        invalid_cases = [
            "",
            "!!!invalid-base64???",
            "bm93",  # base64 "now" with no pipe
            "YWJjfDEyMw",  # "abc|123" with invalid isoformat
            "MjAyNi0xMC0yMnxub3RfYW5faW50",  # "2026-10-22|not_an_int"
        ]
        for bad in invalid_cases:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError) as ctx:
                    decode_cursor(bad)
                self.assertIn("Invalid pagination cursor", str(ctx.exception))
