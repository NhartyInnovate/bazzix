import unittest
from app.db.database import Base
from app.models import (
    User,
    Conversation,
    Message,
    Wallet,
    LedgerTransaction,
    AIRequestLog,
    Subscription,
    Purchase,
    AdminAuditLog,
)

class TestAlembicRegistration(unittest.TestCase):
    def test_all_nine_models_registered_in_metadata(self):
        expected_tables = {
            "users",
            "conversations",
            "messages",
            "wallets",
            "ledger_transactions",
            "ai_request_logs",
            "subscriptions",
            "purchases",
            "admin_audit_logs",
        }
        actual_tables = set(Base.metadata.tables.keys())
        missing = expected_tables - actual_tables
        self.assertEqual(missing, set(), f"Tables missing from Base.metadata: {missing}")

if __name__ == '__main__':
    unittest.main()
