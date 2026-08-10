import unittest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from app.main import app
from app.schemas.user import UserCreate

class TestPasswordValidation(unittest.TestCase):
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
            with self.assertRaises(ValidationError, msg=f"Password '{pwd}' should be rejected."):
                UserCreate(first_name="Test", last_name="User", email="test@example.com", password=pwd)

    def test_schema_validation_length(self):
        # 11 characters
        with self.assertRaises(ValidationError):
            UserCreate(first_name="Test", last_name="User", email="test@example.com", password="strng" * 2 + "1") # 11 chars
        
        # 129 characters
        with self.assertRaises(ValidationError):
            UserCreate(first_name="Test", last_name="User", email="test@example.com", password="a" * 129)
            
        # 12 characters (valid)
        try:
            UserCreate(first_name="Test", last_name="User", email="test@example.com", password="strongpass!1")
        except ValidationError:
            self.fail("12 character strong password raised ValidationError unexpectedly!")

        # 128 characters (valid)
        try:
            long_pass = "strongpass" * 12 + "secure!!"
            UserCreate(first_name="Test", last_name="User", email="test@example.com", password=long_pass)
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

if __name__ == '__main__':
    unittest.main()
