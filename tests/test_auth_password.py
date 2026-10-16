import unittest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from app.main import app
from app.schemas.user import UserCreate, validate_password_strength
from app.schemas.auth import ResetPasswordRequest

class TestPasswordValidation(unittest.TestCase):
    def setUp(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool
        from app.db.database import Base
        from app.db.dependencies import get_db

        self.engine = create_engine('sqlite:///:memory:', connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()
        app.dependency_overrides[get_db] = override_get_db

    def tearDown(self):
        app.dependency_overrides.clear()
        from app.db.database import Base
        Base.metadata.drop_all(self.engine)

    def test_direct_validate_password_strength(self):
        # Common passwords
        for pwd in ["password", "password123", "passwordpassword", "12345678", "qwerty123456"]:
            with self.assertRaises(ValueError):
                validate_password_strength(pwd)

        # Repeating characters
        for pwd in ["aaaaaaaaaaaa", "111111111111", "############"]:
            with self.assertRaises(ValueError):
                validate_password_strength(pwd)

        # Sequential patterns
        for pwd in ["abc12345678xyz", "prefix_abcdefgh_suffix"]:
            with self.assertRaises(ValueError):
                validate_password_strength(pwd)

        # Valid strong password passes through
        strong = "Correct-Horse-Battery-Staple-42!"
        self.assertEqual(validate_password_strength(strong), strong)

    def test_schema_validation_weak(self):
        weak_passwords = [
            "12345678",
            "123456789012",
            "password123",
            "111111111111",
            "aaaaaaaaaaaa",
            "qwerty123456",
        ]
        for pwd in weak_passwords:
            with self.assertRaises(ValidationError, msg=f"UserCreate password '{pwd}' should be rejected."):
                UserCreate(first_name="Test", last_name="User", email="test@example.com", password=pwd)
            with self.assertRaises(ValidationError, msg=f"ResetPasswordRequest password '{pwd}' should be rejected."):
                ResetPasswordRequest(token="dummy_token", new_password=pwd)

    def test_schema_validation_length(self):
        # 11 characters
        with self.assertRaises(ValidationError):
            UserCreate(first_name="Test", last_name="User", email="test@example.com", password="strng" * 2 + "1") # 11 chars
        with self.assertRaises(ValidationError):
            ResetPasswordRequest(token="dummy_token", new_password="strng" * 2 + "1")

        # 129 characters
        with self.assertRaises(ValidationError):
            UserCreate(first_name="Test", last_name="User", email="test@example.com", password="a" * 129)
        with self.assertRaises(ValidationError):
            ResetPasswordRequest(token="dummy_token", new_password="a" * 129)

        # 12 characters (valid)
        try:
            UserCreate(first_name="Test", last_name="User", email="test@example.com", password="strongpass!1")
            ResetPasswordRequest(token="dummy_token", new_password="strongpass!1")
        except ValidationError:
            self.fail("12 character strong password raised ValidationError unexpectedly!")

        # 128 characters (valid)
        try:
            long_pass = "strongpass" * 12 + "secure!!"
            UserCreate(first_name="Test", last_name="User", email="test@example.com", password=long_pass)
            ResetPasswordRequest(token="dummy_token", new_password=long_pass)
        except ValidationError:
            self.fail("128 character strong password raised ValidationError unexpectedly!")

    def test_api_registration(self):
        client = TestClient(app)
        
        # Test weak password rejection at API level
        response = client.post("/auth/register", json={
            "first_name": "Test",
            "last_name": "User",
            "email": "testapi1@example.com",
            "password": "password123"
        })
        self.assertEqual(response.status_code, 422, "API should reject weak passwords with 422 Unprocessable Entity")
        
        # Test strong password success at API level
        response = client.post("/auth/register", json={
            "first_name": "Test",
            "last_name": "User",
            "email": "testapi2@example.com",
            "password": "thisisaverystrongpassword"
        })
        self.assertNotEqual(response.status_code, 422, "API should not reject a strong password with a validation error")

    def test_api_reset_password_validation(self):
        client = TestClient(app)

        # Test weak password rejection at API level
        response = client.post("/auth/reset-password", json={
            "token": "fake_token",
            "new_password": "password123"
        })
        self.assertEqual(response.status_code, 422, "API should reject weak passwords for reset-password with 422")

        # Test short password (< 12 chars) rejection at API level
        response = client.post("/auth/reset-password", json={
            "token": "fake_token",
            "new_password": "short1!"
        })
        self.assertEqual(response.status_code, 422, "API should reject short passwords for reset-password with 422")

if __name__ == '__main__':
    unittest.main()
