
import unittest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.database import Base
from app.db.dependencies import get_db
from app.core.dependencies import get_current_user
from app.models.user import User, RoleType

class TestUsersAPI(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = self.SessionLocal()

        self.normal_user = User(
            id=1, first_name="Normal", last_name="User", email="normal@test.com",
            hashed_password="pw", is_active=True, role=RoleType.USER
        )
        self.admin_user = User(
            id=2, first_name="Admin", last_name="User", email="admin@test.com",
            hashed_password="pw", is_active=True, role=RoleType.ADMIN
        )
        self.db.add(self.normal_user)
        self.db.add(self.admin_user)
        self.db.commit()

        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def _set_user(self, user):
        app.dependency_overrides[get_current_user] = lambda: user

    def test_me_endpoint_normal_user(self):
        self._set_user(self.normal_user)
        resp = self.client.get("/users/me")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["id"], 1)
        self.assertEqual(data["first_name"], "Normal")
        self.assertEqual(data["last_name"], "User")
        self.assertEqual(data["email"], "normal@test.com")
        self.assertEqual(data["role"], "USER")

    def test_me_endpoint_admin_user(self):
        self._set_user(self.admin_user)
        resp = self.client.get("/users/me")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["id"], 2)
        self.assertEqual(data["first_name"], "Admin")
        self.assertEqual(data["last_name"], "User")
        self.assertEqual(data["email"], "admin@test.com")
        self.assertEqual(data["role"], "ADMIN")

