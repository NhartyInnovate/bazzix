import random
import sqlite3
import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, event, insert
from sqlalchemy.orm import sessionmaker

from app.crud.message import (
    get_conversation_messages,
    iter_conversation_messages_newest_first,
)
from app.db.database import Base
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import RoleType, User
from app.services.chat import _load_bounded_chat_context
from app.services.context_manager import (
    ContextManager,
    estimate_message_tokens,
    estimate_tokens,
    get_tokenizer,
)


def _standalone_reference_build_context(
    system_prompt: str,
    history: list[dict],
    user_message: str,
    max_input_tokens: int,
    max_output_tokens: int,
) -> dict:
    """
    Exact standalone reference of the original list-based ContextManager.build_context
    algorithm so equivalence assertions cannot share a defect with refactored code.
    """
    system_msg = {"role": "system", "content": system_prompt}
    user_msg = {"role": "user", "content": user_message}
    base_tokens = 3 + estimate_message_tokens(system_msg) + estimate_message_tokens(user_msg)

    final_history = []
    current_tokens = base_tokens
    for msg in reversed(history):
        msg_tokens = estimate_message_tokens(msg)
        if current_tokens + msg_tokens > max_input_tokens:
            break
        current_tokens += msg_tokens
        final_history.insert(0, msg)

    return {
        "estimated_input_tokens": current_tokens,
        "available_output_budget": max(0, max_output_tokens),
        "bounded_history": final_history,
    }


def _legacy_full_history_context(
    db,
    conversation_id: int,
    system_prompt: str,
    user_message: str,
    max_input_tokens: int,
    max_output_tokens: int = 50,
) -> tuple[bool, dict]:
    history = get_conversation_messages(db, conversation_id)
    is_first_message = len(history) == 1
    raw_history = [{"role": msg.role, "content": msg.content} for msg in history[:-1]]
    ctx = ContextManager(
        max_input_tokens=max_input_tokens,
        max_output_tokens=max_output_tokens,
    ).build_context(system_prompt, raw_history, user_message)
    ref_ctx = _standalone_reference_build_context(
        system_prompt, raw_history, user_message, max_input_tokens, max_output_tokens
    )
    assert ctx == ref_ctx, "Public ContextManager.build_context diverged from standalone reference"
    return is_first_message, ctx


class TestContextManager(unittest.TestCase):
    def setUp(self):
        # We set tight bounds for testing the truncation
        self.manager = ContextManager(max_input_tokens=100, max_output_tokens=50)
        self.system_prompt = "You are a helpful assistant."

    def test_estimate_tokens(self):
        # "Hello world" is typically 2 tokens
        tokens = estimate_tokens("Hello world")
        self.assertGreaterEqual(tokens, 1)

    def test_context_bounds_history(self):
        # Create a history where each message is around 20 tokens
        history = [
            {"role": "user", "content": "Message 1 " * 10},
            {"role": "assistant", "content": "Message 2 " * 10},
            {"role": "user", "content": "Message 3 " * 10},
            {"role": "assistant", "content": "Message 4 " * 10},
            {"role": "user", "content": "Message 5 " * 10},
        ]
        
        user_message = "Final message"
        
        result = self.manager.build_context(self.system_prompt, history, user_message)
        
        # It should truncate the older messages
        bounded = result["bounded_history"]
        
        # It definitely shouldn't contain the first message
        self.assertTrue(len(bounded) < len(history))
        
        # Output budget should be preserved
        self.assertEqual(result["available_output_budget"], 50)
        
        # Estimated input tokens should be <= 100
        self.assertLessEqual(result["estimated_input_tokens"], 100)

    def test_system_prompt_and_user_message_retained(self):
        # Even if history is empty, it returns the base tokens
        result = self.manager.build_context(self.system_prompt, [], "Hello")
        
        self.assertEqual(result["bounded_history"], [])
        self.assertGreater(result["estimated_input_tokens"], 0)

    def test_deterministic_tokenizer(self):
        # Test that encoding is deterministic
        tokenizer = get_tokenizer()
        enc1 = tokenizer.encode("deterministic test")
        enc2 = tokenizer.encode("deterministic test")
        self.assertEqual(enc1, enc2)


class TestContextEquivalenceAndEfficiency(unittest.TestCase):
    BATCH_SIZES = (1, 2, 3, 7, 50, 200)
    WORDS = (
        "alpha beta gamma delta pricing model token context window reply idea "
        "angle framework customer budget strategy growth market product user"
    ).split()

    def setUp(self):
        self.db_stats = {
            "select_count": 0,
            "dbapi_rows_fetched": 0,
            "orm_messages_loaded": 0,
        }
        stats_ref = self.db_stats

        class CountingCursor(sqlite3.Cursor):
            def fetchall(self):
                rows = super().fetchall()
                stats_ref["dbapi_rows_fetched"] += len(rows)
                return rows

            def fetchmany(self, size=1):
                rows = super().fetchmany(size)
                stats_ref["dbapi_rows_fetched"] += len(rows)
                return rows

            def fetchone(self):
                row = super().fetchone()
                if row is not None:
                    stats_ref["dbapi_rows_fetched"] += 1
                return row

        class CountingConnection(sqlite3.Connection):
            def cursor(self, factory=CountingCursor):
                return super().cursor(factory)

        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False, "factory": CountingConnection},
        )
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = self.SessionLocal()

        @event.listens_for(self.engine, "after_cursor_execute")
        def _on_cursor_execute(conn, cursor, stmt, params, context, executemany):
            if stmt.lstrip().upper().startswith("SELECT"):
                self.db_stats["select_count"] += 1

        self._on_message_load = lambda target, context: self.db_stats.__setitem__(
            "orm_messages_loaded", self.db_stats["orm_messages_loaded"] + 1
        )
        event.listen(Message, "load", self._on_message_load)

        self.user = User(
            id=1,
            first_name="Alice",
            last_name="Test",
            email="alice@context.test",
            hashed_password="pw",
            is_active=True,
            role=RoleType.USER,
        )
        self.db.add(self.user)
        self.db.commit()

        self.system_prompt = "You are Bazzix, a helpful thinking partner."
        self._next_conv_id = 100
        self._next_msg_id = 1000

    def tearDown(self):
        event.remove(Message, "load", self._on_message_load)
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def _reset_stats(self):
        self.db.expire_all()
        self.db_stats["select_count"] = 0
        self.db_stats["dbapi_rows_fetched"] = 0
        self.db_stats["orm_messages_loaded"] = 0

    def _create_conversation_with_rows(self, rows: list[tuple[int, str, str, datetime | None]]) -> int:
        self._next_conv_id += 1
        conv_id = self._next_conv_id
        self.db.add(Conversation(id=conv_id, title="Conv", is_pinned=False, user_id=self.user.id))
        self.db.flush()
        if rows:
            self.db.execute(
                insert(Message.__table__),
                [
                    {
                        "id": mid,
                        "conversation_id": conv_id,
                        "role": role,
                        "content": content,
                        "created_at": created_at,
                    }
                    for (mid, role, content, created_at) in rows
                ],
            )
        self.db.commit()
        return conv_id

    def _assert_equivalent_for_all_batch_sizes(
        self,
        conv_id: int,
        user_message: str,
        budgets: tuple[int, ...] = (60, 140, 350, 1000, 100000),
    ):
        for budget in budgets:
            expected_first, expected_ctx = _legacy_full_history_context(
                self.db,
                conv_id,
                self.system_prompt,
                user_message,
                max_input_tokens=budget,
                max_output_tokens=50,
            )
            for bs in self.BATCH_SIZES:
                mgr = ContextManager(max_input_tokens=budget, max_output_tokens=50)
                actual_first, actual_ctx = _load_bounded_chat_context(
                    db=self.db,
                    conversation_id=conv_id,
                    user_message=user_message,
                    system_prompt=self.system_prompt,
                    context_manager=mgr,
                    batch_size=bs,
                )
                self.assertEqual(
                    actual_first,
                    expected_first,
                    f"is_first_message mismatch for conv={conv_id} budget={budget} batch_size={bs}",
                )
                self.assertEqual(
                    actual_ctx["bounded_history"],
                    expected_ctx["bounded_history"],
                    f"bounded_history mismatch for conv={conv_id} budget={budget} batch_size={bs}",
                )
                self.assertEqual(
                    actual_ctx["estimated_input_tokens"],
                    expected_ctx["estimated_input_tokens"],
                    f"estimated_input_tokens mismatch for conv={conv_id} budget={budget} batch_size={bs}",
                )
                self.assertEqual(
                    actual_ctx["available_output_budget"],
                    expected_ctx["available_output_budget"],
                    f"available_output_budget mismatch for conv={conv_id} budget={budget} batch_size={bs}",
                )

    def test_empty_single_two_and_short_conversations(self):
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)

        # 0 messages
        conv_empty = self._create_conversation_with_rows([])
        self._assert_equivalent_for_all_batch_sizes(conv_empty, "Hello")

        # 1 message (must trigger first-message title flag and empty bounded_history)
        conv_one = self._create_conversation_with_rows(
            [(1, "user", "First message", base)]
        )
        self._assert_equivalent_for_all_batch_sizes(conv_one, "First message")
        is_first, ctx = _load_bounded_chat_context(
            self.db, conv_one, "First message", self.system_prompt, ContextManager(1000, 50), batch_size=1
        )
        self.assertTrue(is_first)
        self.assertEqual(ctx["bounded_history"], [])

        # 2 messages (must NOT trigger first-message title flag, includes first message)
        conv_two = self._create_conversation_with_rows(
            [
                (2, "user", "First user question", base),
                (3, "assistant", "First assistant reply", base + timedelta(seconds=1)),
            ]
        )
        self._assert_equivalent_for_all_batch_sizes(conv_two, "Second user question")
        is_first_two, ctx_two = _load_bounded_chat_context(
            self.db, conv_two, "Second user question", self.system_prompt, ContextManager(1000, 50), batch_size=1
        )
        self.assertFalse(is_first_two)
        self.assertEqual(len(ctx_two["bounded_history"]), 1)
        self.assertEqual(ctx_two["bounded_history"][0]["content"], "First user question")

    def test_single_prior_message_exceeding_budget_stops_without_skipping(self):
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        # Older message is tiny (would fit if oversized message were skipped),
        # newest prior message is huge (exceeds budget). Must stop at huge message and return [].
        conv_id = self._create_conversation_with_rows(
            [
                (10, "user", "tiny older message", base),
                (11, "assistant", "oversized message " * 200, base + timedelta(seconds=1)),
                (12, "user", "current user message", base + timedelta(seconds=2)),
            ]
        )
        self._assert_equivalent_for_all_batch_sizes(conv_id, "current user message", budgets=(120, 200))
        _, ctx = _load_bounded_chat_context(
            self.db, conv_id, "current user message", self.system_prompt, ContextManager(150, 50), batch_size=2
        )
        self.assertEqual(ctx["bounded_history"], [])

    def test_system_plus_user_message_already_exceeds_budget(self):
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        conv_id = self._create_conversation_with_rows(
            [
                (20, "user", "short 1", base),
                (21, "assistant", "short 2", base + timedelta(seconds=1)),
                (22, "user", "huge current message " * 100, base + timedelta(seconds=2)),
            ]
        )
        huge_user_msg = "huge current message " * 100
        self._assert_equivalent_for_all_batch_sizes(conv_id, huge_user_msg, budgets=(50, 100))
        _, ctx = _load_bounded_chat_context(
            self.db, conv_id, huge_user_msg, self.system_prompt, ContextManager(50, 50), batch_size=1
        )
        self.assertEqual(ctx["bounded_history"], [])
        self.assertGreater(ctx["estimated_input_tokens"], 50)

    def test_duplicate_timestamps_across_batch_boundaries(self):
        tied_ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        rows = [
            (100 + i, "user" if i % 2 == 0 else "assistant", f"Tied message number {i} with content", tied_ts)
            for i in range(25)
        ]
        conv_id = self._create_conversation_with_rows(rows)
        self._assert_equivalent_for_all_batch_sizes(
            conv_id, "Latest tied message", budgets=(80, 160, 300, 600, 100000)
        )

    def test_backdated_timestamps_and_positional_exclusion(self):
        base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        # Higher ID (205) has an OLDER timestamp than lower ID (204).
        # Canonical order (created_at ASC, id ASC) places 204 last, so history[:-1] drops 204 by position.
        rows = [
            (201, "user", "Message 201 earliest", base - timedelta(minutes=10)),
            (205, "assistant", "Message 205 higher ID but older timestamp", base - timedelta(minutes=5)),
            (202, "user", "Message 202 middle", base - timedelta(minutes=3)),
            (203, "assistant", "Message 203 tied timestamp low ID", base - timedelta(minutes=1)),
            (206, "user", "Message 206 tied timestamp high ID", base - timedelta(minutes=1)),
            (204, "user", "Message 204 lower ID but newest timestamp", base),
        ]
        conv_id = self._create_conversation_with_rows(rows)
        self._assert_equivalent_for_all_batch_sizes(
            conv_id, "Message 204 lower ID but newest timestamp", budgets=(80, 150, 250, 100000)
        )

    def test_null_timestamps_preserved_across_all_positions_and_batch_sizes(self):
        base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        # Case A: NULL timestamp on an older message, plus non-NULL newer messages
        conv_null_mid = self._create_conversation_with_rows(
            [
                (301, "user", "Message 301 with timestamp", base),
                (302, "assistant", "Message 302 with NULL timestamp", None),
                (303, "user", "Message 303 with later timestamp", base + timedelta(seconds=10)),
                (304, "assistant", "Message 304 with newest timestamp", base + timedelta(seconds=20)),
            ]
        )
        self._assert_equivalent_for_all_batch_sizes(
            conv_null_mid, "Follow-up question", budgets=(70, 120, 200, 100000)
        )

        # Case B: Multiple NULL timestamps mixed with tied non-NULL timestamps
        conv_multi_null = self._create_conversation_with_rows(
            [
                (310, "user", "Null msg A", None),
                (311, "assistant", "Null msg B", None),
                (312, "user", "Timed msg C", base),
                (313, "assistant", "Timed msg D", base),
                (314, "user", "Null msg E", None),
                (315, "user", "Timed msg F", base + timedelta(seconds=5)),
            ]
        )
        self._assert_equivalent_for_all_batch_sizes(
            conv_multi_null, "Timed msg F", budgets=(60, 110, 180, 100000)
        )

        # Case C: Single message with NULL timestamp (title trigger must still be True)
        conv_single_null = self._create_conversation_with_rows(
            [(320, "user", "Only message has null timestamp", None)]
        )
        self._assert_equivalent_for_all_batch_sizes(conv_single_null, "Only message has null timestamp")

    def test_randomized_property_equivalence(self):
        rng = random.Random(20261022)
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        msg_id = 5000

        for seed_idx in range(60):
            n_msgs = rng.randint(0, 35)
            rows = []
            cur_ts = base
            for _ in range(n_msgs):
                msg_id += 1
                r = rng.random()
                if r < 0.10:
                    ts = None
                elif r < 0.40:
                    ts = cur_ts  # duplicate timestamp
                elif r < 0.55:
                    cur_ts = cur_ts - timedelta(seconds=rng.randint(1, 5))  # backdated
                    ts = cur_ts
                else:
                    cur_ts = cur_ts + timedelta(seconds=rng.randint(1, 5))
                    ts = cur_ts
                word_count = rng.choice([1, 4, 15, 45, 120])
                content = " ".join(rng.choice(self.WORDS) for _ in range(word_count))
                role = "user" if rng.random() < 0.5 else "assistant"
                rows.append((msg_id, role, content, ts))

            conv_id = self._create_conversation_with_rows(rows)
            user_msg = " ".join(rng.choice(self.WORDS) for _ in range(rng.choice([2, 20, 200])))
            self._assert_equivalent_for_all_batch_sizes(
                conv_id, user_msg, budgets=(60, 150, 400, 100000)
            )

    def test_database_efficiency_large_conversation_small_suffix(self):
        """
        Case 1: 500 messages in conversation (~25 tokens each), token budget allows only ~10 messages.
        With batch_size=50, the optimized loader must stop after the first batch of 50 rows
        instead of loading all 500 rows.
        """
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        rows = [
            (
                10000 + i,
                "user" if i % 2 == 0 else "assistant",
                f"Conversation message {i}: " + ("context words " * 8),
                base + timedelta(seconds=i),
            )
            for i in range(500)
        ]
        conv_id = self._create_conversation_with_rows(rows)
        budget = 300  # Fits roughly 10 messages

        # Measure legacy full-history path
        self._reset_stats()
        expected_first, expected_ctx = _legacy_full_history_context(
            self.db, conv_id, self.system_prompt, "Next question", max_input_tokens=budget
        )
        legacy_stats = dict(self.db_stats)

        # Measure optimized batched path (batch_size=50)
        self._reset_stats()
        actual_first, actual_ctx = _load_bounded_chat_context(
            db=self.db,
            conversation_id=conv_id,
            user_message="Next question",
            system_prompt=self.system_prompt,
            context_manager=ContextManager(max_input_tokens=budget, max_output_tokens=50),
            batch_size=50,
        )
        opt_stats = dict(self.db_stats)

        # Context must be 100% identical
        self.assertEqual(actual_first, expected_first)
        self.assertEqual(actual_ctx, expected_ctx)
        self.assertGreater(len(actual_ctx["bounded_history"]), 0)
        self.assertLess(len(actual_ctx["bounded_history"]), 25)

        # Legacy loaded all 500 rows; optimized loaded only 1 batch of 50 rows (plus 0-row NULL preflight)
        self.assertEqual(legacy_stats["select_count"], 1)
        self.assertEqual(legacy_stats["dbapi_rows_fetched"], 500)
        self.assertEqual(legacy_stats["orm_messages_loaded"], 500)

        self.assertEqual(opt_stats["select_count"], 2)  # 1 NULL preflight + 1 batch
        self.assertEqual(opt_stats["dbapi_rows_fetched"], 50)
        self.assertEqual(opt_stats["orm_messages_loaded"], 50)

    def test_database_efficiency_conversation_fitting_within_budget(self):
        """
        Case 2: 40 messages that all fit within a 100,000-token budget.
        With default batch_size=200, executes 1 NULL preflight (0 rows) + 1 batch SELECT (40 rows).
        """
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        rows = [
            (20000 + i, "user" if i % 2 == 0 else "assistant", f"Short message {i}", base + timedelta(seconds=i))
            for i in range(40)
        ]
        conv_id = self._create_conversation_with_rows(rows)

        self._reset_stats()
        expected_first, expected_ctx = _legacy_full_history_context(
            self.db, conv_id, self.system_prompt, "Hello", max_input_tokens=100000
        )
        legacy_stats = dict(self.db_stats)

        self._reset_stats()
        actual_first, actual_ctx = _load_bounded_chat_context(
            db=self.db,
            conversation_id=conv_id,
            user_message="Hello",
            system_prompt=self.system_prompt,
            context_manager=ContextManager(max_input_tokens=100000, max_output_tokens=50),
            batch_size=200,
        )
        opt_stats = dict(self.db_stats)

        self.assertEqual(actual_first, expected_first)
        self.assertEqual(actual_ctx, expected_ctx)
        self.assertEqual(len(actual_ctx["bounded_history"]), 39)

        self.assertEqual(legacy_stats["select_count"], 1)
        self.assertEqual(legacy_stats["dbapi_rows_fetched"], 40)

        self.assertEqual(opt_stats["select_count"], 2)
        self.assertEqual(opt_stats["dbapi_rows_fetched"], 40)
        self.assertEqual(opt_stats["orm_messages_loaded"], 40)

    def test_database_efficiency_null_timestamp_fallback(self):
        """
        Case 3: Conversation containing a NULL timestamp triggers the preflight fallback
        to get_conversation_messages, preserving all rows without silent omission.
        """
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        rows = [
            (
                30000 + i,
                "user" if i % 2 == 0 else "assistant",
                f"Msg {i}",
                None if i == 10 else base + timedelta(seconds=i),
            )
            for i in range(60)
        ]
        conv_id = self._create_conversation_with_rows(rows)

        self._reset_stats()
        expected_first, expected_ctx = _legacy_full_history_context(
            self.db, conv_id, self.system_prompt, "Hello", max_input_tokens=100000
        )

        self._reset_stats()
        actual_first, actual_ctx = _load_bounded_chat_context(
            db=self.db,
            conversation_id=conv_id,
            user_message="Hello",
            system_prompt=self.system_prompt,
            context_manager=ContextManager(max_input_tokens=100000, max_output_tokens=50),
            batch_size=20,
        )
        fallback_stats = dict(self.db_stats)

        self.assertEqual(actual_first, expected_first)
        self.assertEqual(actual_ctx, expected_ctx)
        self.assertEqual(len(actual_ctx["bounded_history"]), 59)
        # 1 preflight SELECT (returns 1 row) + 1 fallback full-history SELECT (returns 60 rows)
        self.assertEqual(fallback_stats["select_count"], 2)
        self.assertEqual(fallback_stats["dbapi_rows_fetched"], 61)
        self.assertEqual(fallback_stats["orm_messages_loaded"], 60)

    def test_invalid_batch_size_raises_value_error(self):
        with self.assertRaises(ValueError):
            list(iter_conversation_messages_newest_first(self.db, 999, batch_size=0))


if __name__ == "__main__":
    unittest.main()
