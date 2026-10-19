import unittest
import time
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.database import Base
from app.db.dependencies import get_db
from app.core.dependencies import get_current_user
from app.models.user import User, RoleType
from app.core.auth import (
    create_verification_token,
    verify_verification_token,
    create_reset_token,
)
from app.core.rate_limit import rate_limit_records
from app.api.auth import verification_resend_records


class TestEmailVerificationAPI(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = self.SessionLocal()

        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app, raise_server_exceptions=False)

        # Clear in-memory rate limit caches
        rate_limit_records.clear()
        verification_resend_records.clear()

        # Seed unverified test user
        self.unverified_user = User(
            id=10,
            first_name="Alice",
            last_name="Unverified",
            email="alice@example.com",
            hashed_password="hashed_pw_dummy",
            is_active=True,
            is_verified=False,
            role=RoleType.USER,
        )
        # Seed verified test user
        self.verified_user = User(
            id=20,
            first_name="Bob",
            last_name="Verified",
            email="bob@example.com",
            hashed_password="hashed_pw_dummy",
            is_active=True,
            is_verified=True,
            role=RoleType.USER,
        )
        self.db.add(self.unverified_user)
        self.db.add(self.verified_user)
        self.db.commit()

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        Base.metadata.drop_all(self.engine)
        rate_limit_records.clear()
        verification_resend_records.clear()

    def test_users_me_returns_is_verified_boolean(self):
        # 1. Unverified user
        app.dependency_overrides[get_current_user] = lambda: self.unverified_user
        res = self.client.get("/users/me")
        self.assertEqual(res.status_code, 200)
        self.assertIs(res.json()["is_verified"], False)

        # 2. Verified user
        app.dependency_overrides[get_current_user] = lambda: self.verified_user
        res = self.client.get("/users/me")
        self.assertEqual(res.status_code, 200)
        self.assertIs(res.json()["is_verified"], True)

        # 3. Legacy user with None/NULL is_verified
        legacy_user = User(
            id=30,
            first_name="Legacy",
            last_name="User",
            email="legacy@example.com",
            hashed_password="pw",
            is_active=True,
            is_verified=None,
            role=RoleType.USER,
        )
        app.dependency_overrides[get_current_user] = lambda: legacy_user
        res = self.client.get("/users/me")
        self.assertEqual(res.status_code, 200)
        self.assertIs(res.json()["is_verified"], False)

    def test_valid_token_successfully_verifies_account(self):
        token = create_verification_token(self.unverified_user.id, self.unverified_user.email)

        res = self.client.post("/auth/verify-email", json={"token": token})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["is_verified"])
        self.assertEqual(res.json()["message"], "Email verified successfully.")

        # Confirm in database
        self.db.expire_all()
        refreshed_user = self.db.query(User).filter(User.id == self.unverified_user.id).first()
        self.assertTrue(refreshed_user.is_verified)

    def test_verify_email_is_idempotent(self):
        token = create_verification_token(self.verified_user.id, self.verified_user.email)

        res = self.client.post("/auth/verify-email", json={"token": token})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["is_verified"])
        self.assertEqual(res.json()["message"], "Email is already verified.")

    def test_malformed_and_tampered_tokens_rejected(self):
        # 1. Non-JWT garbage string
        res = self.client.post("/auth/verify-email", json={"token": "garbage-string"})
        self.assertEqual(res.status_code, 400)
        err_msg = res.json().get("message") or res.json().get("detail")
        self.assertIn("Invalid or expired", err_msg)

        # 2. Tampered JWT
        valid_token = create_verification_token(self.unverified_user.id, self.unverified_user.email)
        tampered_token = valid_token[:-4] + "abcd"
        res = self.client.post("/auth/verify-email", json={"token": tampered_token})
        self.assertEqual(res.status_code, 400)
        err_msg = res.json().get("message") or res.json().get("detail")
        self.assertIn("Invalid or expired", err_msg)

    def test_expired_token_rejected(self):
        from datetime import datetime, timedelta, timezone
        from jose import jwt
        from app.core.auth import _get_secret_key
        from app.core.config import settings

        # Token created with past expiry
        past_time = datetime.now(timezone.utc) - timedelta(hours=25)
        expired_token = jwt.encode(
            {
                "sub": str(self.unverified_user.id),
                "email": self.unverified_user.email,
                "type": "verification",
                "exp": past_time,
            },
            _get_secret_key(),
            algorithm=settings.ALGORITHM,
        )

        res = self.client.post("/auth/verify-email", json={"token": expired_token})
        self.assertEqual(res.status_code, 400)
        err_msg = res.json().get("message") or res.json().get("detail")
        self.assertIn("Invalid or expired", err_msg)

    def test_wrong_purpose_token_rejected(self):
        # Password reset token cannot be used to verify email
        reset_token = create_reset_token(self.unverified_user.email)
        res = self.client.post("/auth/verify-email", json={"token": reset_token})
        self.assertEqual(res.status_code, 400)
        err_msg = res.json().get("message") or res.json().get("detail")
        self.assertIn("Invalid or expired", err_msg)

        # Verification token cannot be used to reset password
        verification_token = create_verification_token(self.unverified_user.id, self.unverified_user.email)
        res = self.client.post(
            "/auth/reset-password",
            json={"token": verification_token, "new_password": "NewStrongPassphrase123!"},
        )
        self.assertEqual(res.status_code, 400)
        err_msg = res.json().get("message") or res.json().get("detail")
        self.assertIn("Invalid or expired", err_msg)

        # Verification token cannot be used as an access token
        from app.core.auth import verify_access_token
        self.assertIsNone(verify_access_token(verification_token))

    def test_token_email_mismatch_rejected(self):
        # Token generated for another email address
        mismatched_token = create_verification_token(self.unverified_user.id, "different@example.com")
        res = self.client.post("/auth/verify-email", json={"token": mismatched_token})
        self.assertEqual(res.status_code, 400)
        err_msg = res.json().get("message") or res.json().get("detail")
        self.assertIn("not valid for this account email", err_msg)

    def test_unauthenticated_resend_rejected(self):
        # Calling resend without token override or bearer auth returns 401
        res = self.client.post("/auth/resend-verification")
        self.assertEqual(res.status_code, 401)

    def test_already_verified_resend_does_not_send_email(self):
        app.dependency_overrides[get_current_user] = lambda: self.verified_user

        with patch("app.api.auth.send_verification_email") as mock_send:
            res = self.client.post("/auth/resend-verification")
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json()["message"], "Your email is already verified.")
            self.assertTrue(res.json()["is_verified"])
            mock_send.assert_not_called()

    def test_resend_cooldown_and_hourly_limit(self):
        app.dependency_overrides[get_current_user] = lambda: self.unverified_user

        with patch("app.api.auth.send_verification_email") as mock_send:
            # First request succeeds
            res1 = self.client.post("/auth/resend-verification")
            self.assertEqual(res1.status_code, 200)
            self.assertEqual(res1.json()["message"], "Verification email sent. Please check your inbox.")
            self.assertEqual(mock_send.call_count, 1)

            # Immediate second request triggers 60-second cooldown (429)
            res2 = self.client.post("/auth/resend-verification")
            self.assertEqual(res2.status_code, 429)
            err_msg2 = res2.json().get("message") or res2.json().get("detail")
            self.assertIn("Please wait", err_msg2)
            self.assertEqual(mock_send.call_count, 1)

            # Fast-forward timestamps to test 5-email hourly limit
            user_id = self.unverified_user.id
            now = time.time()
            # Simulate 5 requests within the last hour spaced > 60s apart
            verification_resend_records[user_id] = [
                now - 3000,
                now - 2400,
                now - 1800,
                now - 1200,
                now - 500,
            ]

            # 6th request within the hour should trigger hourly cap 429
            res3 = self.client.post("/auth/resend-verification")
            self.assertEqual(res3.status_code, 429)
            err_msg3 = res3.json().get("message") or res3.json().get("detail")
            self.assertIn("Verification email limit reached", err_msg3)

    def test_registration_queues_welcome_and_verification_emails(self):
        with patch("app.api.auth.send_welcome_email") as mock_welcome, \
             patch("app.api.auth.send_verification_email") as mock_verify:
            res = self.client.post("/auth/register", json={
                "first_name": "New",
                "last_name": "User",
                "email": "newuser@example.com",
                "password": "ValidStrongPassword123!",
            })
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["message"], "User registered successfully!")
            self.assertEqual(data["user"]["email"], "newuser@example.com")

            # Check both background tasks were queued
            mock_welcome.assert_called_once_with("newuser@example.com")
            mock_verify.assert_called_once()
            args, kwargs = mock_verify.call_args
            self.assertEqual(args[0], "newuser@example.com")
            # Verify token is valid
            token_payload = verify_verification_token(args[1])
            self.assertIsNotNone(token_payload)
            self.assertEqual(token_payload["email"], "newuser@example.com")

    def test_email_dispatch_failure_does_not_break_registration(self):
        # Simulate send_welcome_email and send_verification_email raising exceptions
        with patch("app.api.auth.send_welcome_email", side_effect=RuntimeError("Resend down")), \
             patch("app.api.auth.send_verification_email", side_effect=RuntimeError("SMTP error")):
            res = self.client.post("/auth/register", json={
                "first_name": "FailEmail",
                "last_name": "User",
                "email": "failemail@example.com",
                "password": "ValidStrongPassword123!",
            })
            # Registration itself completes with 200 OK because email failures in background tasks don't break response
            self.assertEqual(res.status_code, 200)

            # Confirm user was safely created in database
            self.db.expire_all()
            created = self.db.query(User).filter(User.email == "failemail@example.com").first()
            self.assertIsNotNone(created)
            self.assertFalse(created.is_verified)


if __name__ == "__main__":
    unittest.main()
