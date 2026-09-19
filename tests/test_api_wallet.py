import unittest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.database import Base
from app.db.dependencies import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.wallet import Wallet

class TestWalletAPI(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            'sqlite:///:memory:', 
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = self.SessionLocal()

        self.user = User(
            id=1,
            first_name="Test",
            last_name="User",
            email="test@example.com",
            hashed_password="pw",
            is_active=True
        )
        self.db.add(self.user)
        self.db.commit()

        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        def override_get_current_user():
            return self.user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def test_wallet_exists(self):
        wallet = Wallet(
            user_id=self.user.id,
            subscription_balance=1000,
            purchased_balance=500,
            reserved_balance=200
        )
        self.db.add(wallet)
        self.db.commit()

        response = self.client.get("/users/me/wallet")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["subscription_balance"], 1000)
        self.assertEqual(data["purchased_balance"], 500)
        self.assertEqual(data["reserved_balance"], 200)
        self.assertEqual(data["available_credits"], 1300)

    def test_wallet_does_not_exist(self):
        response = self.client.get("/users/me/wallet")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["subscription_balance"], 0)
        self.assertEqual(data["purchased_balance"], 0)
        self.assertEqual(data["reserved_balance"], 0)
        self.assertEqual(data["available_credits"], 0)

        # Verify wallet was NOT created
        wallets = self.db.query(Wallet).all()
        self.assertEqual(len(wallets), 0)

    def test_unauthenticated(self):
        app.dependency_overrides.clear()
        response = self.client.get("/users/me/wallet")
        self.assertEqual(response.status_code, 401)
