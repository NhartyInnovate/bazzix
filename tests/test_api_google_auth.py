import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import IntegrityError
from google.auth.exceptions import GoogleAuthError

from app.main import app
from app.db.database import Base
from app.db.dependencies import get_db
from app.models.user import User, RoleType
from app.models.wallet import Wallet
from app.models.subscription import Subscription
from app.core.config import settings
from app.core.auth import verify_access_token
from app.core.rate_limit import rate_limit_records


TEST_CLIENT_ID = "mock-google-client-id-12345.apps.googleusercontent.com"


class TestGoogleAuthAPI(unittest.TestCase):
    def setUp(self):
        self.original_client_id = settings.GOOGLE_CLIENT_ID
        settings.GOOGLE_CLIENT_ID = TEST_CLIENT_ID

        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = self.SessionLocal()

        def override_get_db():
            yield self.db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app, raise_server_exceptions=False)
        rate_limit_records.clear()

    def tearDown(self):
        settings.GOOGLE_CLIENT_ID = self.original_client_id
        app.dependency_overrides.clear()
        self.db.close()
        Base.metadata.drop_all(self.engine)
        rate_limit_records.clear()

    def _mock_google_payload(self, **overrides):
        payload = {
            "iss": "https://accounts.google.com",
            "aud": TEST_CLIENT_ID,
            "sub": "google-user-id-999",
            "email": "googleuser@example.com",
            "email_verified": True,
            "given_name": "Google",
            "family_name": "Tester",
            "name": "Google Tester",
        }
        payload.update(overrides)
        return payload

    @patch("app.api.auth.send_welcome_email")
    @patch("app.api.auth.id_token.verify_oauth2_token")
    def test_new_user_registration_success(self, mock_verify, mock_send_welcome):
        mock_verify.return_value = self._mock_google_payload()

        res = self.client.post("/auth/google", json={"credential": "valid.mock.token"})
        self.assertEqual(res.status_code, 200)

        data = res.json()
        self.assertIn("access_token", data)
        self.assertEqual(data["token_type"], "bearer")

        # Verify JWT subject matches created user ID
        token_payload = verify_access_token(data["access_token"])
        self.assertIsNotNone(token_payload)

        # Inspect persisted user
        created_user = self.db.query(User).filter(User.email == "googleuser@example.com").first()
        self.assertIsNotNone(created_user)
        self.assertEqual(str(created_user.id), token_payload["sub"])
        self.assertEqual(created_user.first_name, "Google")
        self.assertEqual(created_user.last_name, "Tester")
        self.assertTrue(created_user.is_verified)
        self.assertTrue(created_user.is_active)
        self.assertEqual(created_user.role, RoleType.USER)
        self.assertTrue(len(created_user.hashed_password) > 20)

        # Confirm wallet provisioning
        wallet = self.db.query(Wallet).filter(Wallet.user_id == created_user.id).first()
        self.assertIsNotNone(wallet)
        self.assertGreater(wallet.subscription_balance, 0)

        # Confirm subscription
        subscription = self.db.query(Subscription).filter(Subscription.user_id == created_user.id).first()
        self.assertIsNotNone(subscription)
        self.assertEqual(subscription.plan_id, "free")

        # Confirm welcome email queued
        mock_send_welcome.assert_called_once_with("googleuser@example.com")

    @patch("app.api.auth.id_token.verify_oauth2_token")
    def test_name_parsing_fallbacks(self, mock_verify):
        # 1. Fallback to full `name` if given_name is missing
        mock_verify.return_value = self._mock_google_payload(
            email="fullname@example.com",
            given_name="",
            family_name="",
            name="Jane Doe",
        )
        res = self.client.post("/auth/google", json={"credential": "valid.mock.token"})
        self.assertEqual(res.status_code, 200)
        user = self.db.query(User).filter(User.email == "fullname@example.com").first()
        self.assertIsNotNone(user)
        self.assertEqual(user.first_name, "Jane")
        self.assertEqual(user.last_name, "Doe")

        # 2. Fallback to email username if all name claims are missing
        mock_verify.return_value = self._mock_google_payload(
            email="nonameuser@example.com",
            given_name="",
            family_name="",
            name="",
        )
        res = self.client.post("/auth/google", json={"credential": "valid.mock.token"})
        self.assertEqual(res.status_code, 200)
        user2 = self.db.query(User).filter(User.email == "nonameuser@example.com").first()
        self.assertIsNotNone(user2)
        self.assertEqual(user2.first_name, "nonameuser")
        self.assertEqual(user2.last_name, "")

    @patch("app.api.auth.id_token.verify_oauth2_token")
    def test_returning_google_user(self, mock_verify):
        mock_verify.return_value = self._mock_google_payload(email="returning@example.com")

        # First login (creation)
        res1 = self.client.post("/auth/google", json={"credential": "valid.token.1"})
        self.assertEqual(res1.status_code, 200)

        user = self.db.query(User).filter(User.email == "returning@example.com").first()
        original_hash = user.hashed_password
        wallet = self.db.query(Wallet).filter(Wallet.user_id == user.id).first()
        initial_balance = wallet.subscription_balance

        # Second login
        res2 = self.client.post("/auth/google", json={"credential": "valid.token.2"})
        self.assertEqual(res2.status_code, 200)

        self.db.expire_all()
        user_after = self.db.query(User).filter(User.email == "returning@example.com").first()
        self.assertEqual(user_after.hashed_password, original_hash)

        # Ensure no duplicate wallets created
        wallets = self.db.query(Wallet).filter(Wallet.user_id == user.id).all()
        self.assertEqual(len(wallets), 1)
        self.assertEqual(wallets[0].subscription_balance, initial_balance)

    @patch("app.api.auth.id_token.verify_oauth2_token")
    def test_existing_password_user_linking(self, mock_verify):
        # User created originally with email/password
        existing_pw_hash = "argon2id$existing$preconfigured$hash"
        existing_user = User(
            id=101,
            first_name="Original",
            last_name="PasswordUser",
            email="existing_pw@example.com",
            hashed_password=existing_pw_hash,
            is_active=True,
            is_verified=True,
            role=RoleType.USER,
        )
        self.db.add(existing_user)
        self.db.commit()

        mock_verify.return_value = self._mock_google_payload(email="existing_pw@example.com")

        res = self.client.post("/auth/google", json={"credential": "valid.mock.token"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("access_token", data)

        # Verify password hash was NOT overwritten
        self.db.expire_all()
        refreshed = self.db.query(User).filter(User.id == 101).first()
        self.assertEqual(refreshed.hashed_password, existing_pw_hash)

    @patch("app.api.auth.id_token.verify_oauth2_token")
    def test_existing_unverified_user_auto_verified(self, mock_verify):
        # User created but email was never verified
        unverified = User(
            id=102,
            first_name="Unverified",
            last_name="User",
            email="unverified_existing@example.com",
            hashed_password="hashed_pw_dummy",
            is_active=True,
            is_verified=False,
            role=RoleType.USER,
        )
        self.db.add(unverified)
        self.db.commit()

        mock_verify.return_value = self._mock_google_payload(email="unverified_existing@example.com")

        res = self.client.post("/auth/google", json={"credential": "valid.mock.token"})
        self.assertEqual(res.status_code, 200)

        # Confirm account is now marked verified
        self.db.expire_all()
        refreshed = self.db.query(User).filter(User.id == 102).first()
        self.assertTrue(refreshed.is_verified)

    def _get_error_message(self, res):
        body = res.json()
        return body.get("message") or body.get("detail") or ""

    @patch("app.api.auth.id_token.verify_oauth2_token")
    def test_inactive_user_rejected(self, mock_verify):
        disabled_user = User(
            id=103,
            first_name="Disabled",
            last_name="Account",
            email="disabled@example.com",
            hashed_password="hashed_pw_dummy",
            is_active=False,
            is_verified=True,
            role=RoleType.USER,
        )
        self.db.add(disabled_user)
        self.db.commit()

        mock_verify.return_value = self._mock_google_payload(email="disabled@example.com")

        res = self.client.post("/auth/google", json={"credential": "valid.mock.token"})
        self.assertEqual(res.status_code, 403)
        self.assertIn("disabled", self._get_error_message(res).lower())

    def test_missing_credential_field(self):
        res = self.client.post("/auth/google", json={})
        self.assertEqual(res.status_code, 422)

    def test_empty_or_whitespace_credential(self):
        res1 = self.client.post("/auth/google", json={"credential": ""})
        self.assertEqual(res1.status_code, 422)

        res2 = self.client.post("/auth/google", json={"credential": "   "})
        self.assertEqual(res2.status_code, 422)

    @patch("app.api.auth.id_token.verify_oauth2_token")
    def test_invalid_token_signature(self, mock_verify):
        mock_verify.side_effect = ValueError("Invalid token signature")

        res = self.client.post("/auth/google", json={"credential": "invalid.signature.token"})
        self.assertEqual(res.status_code, 401)
        self.assertEqual(self._get_error_message(res), "Invalid Google credential.")

    @patch("app.api.auth.id_token.verify_oauth2_token")
    def test_expired_token(self, mock_verify):
        mock_verify.side_effect = GoogleAuthError("Token has expired")

        res = self.client.post("/auth/google", json={"credential": "expired.token"})
        self.assertEqual(res.status_code, 401)
        self.assertEqual(self._get_error_message(res), "Invalid Google credential.")

    @patch("app.api.auth.id_token.verify_oauth2_token")
    def test_unexpected_verification_exception(self, mock_verify):
        mock_verify.side_effect = RuntimeError("Network timeout contacting Google certs")

        res = self.client.post("/auth/google", json={"credential": "some.token"})
        self.assertEqual(res.status_code, 401)
        self.assertEqual(self._get_error_message(res), "Invalid Google credential.")

    @patch("app.api.auth.id_token.verify_oauth2_token")
    def test_issuer_validation(self, mock_verify):
        mock_verify.return_value = self._mock_google_payload(iss="https://malicious.issuer.org")

        res = self.client.post("/auth/google", json={"credential": "fake.iss.token"})
        self.assertEqual(res.status_code, 401)
        self.assertEqual(self._get_error_message(res), "Invalid Google credential.")

    @patch("app.api.auth.id_token.verify_oauth2_token")
    def test_audience_validation(self, mock_verify):
        mock_verify.return_value = self._mock_google_payload(aud="attacker-client-id.apps.googleusercontent.com")

        res = self.client.post("/auth/google", json={"credential": "wrong.aud.token"})
        self.assertEqual(res.status_code, 401)
        self.assertEqual(self._get_error_message(res), "Invalid Google credential.")

    @patch("app.api.auth.id_token.verify_oauth2_token")
    def test_missing_email_claim(self, mock_verify):
        # 1. Missing email key
        mock_verify.return_value = self._mock_google_payload(email=None)
        res1 = self.client.post("/auth/google", json={"credential": "valid.token"})
        self.assertEqual(res1.status_code, 400)
        self.assertIn("email is missing", self._get_error_message(res1))

        # 2. Empty string email
        mock_verify.return_value = self._mock_google_payload(email="   ")
        res2 = self.client.post("/auth/google", json={"credential": "valid.token"})
        self.assertEqual(res2.status_code, 400)
        self.assertIn("email is missing", self._get_error_message(res2))

    @patch("app.api.auth.id_token.verify_oauth2_token")
    def test_unverified_email_claim(self, mock_verify):
        mock_verify.return_value = self._mock_google_payload(email_verified=False)

        res = self.client.post("/auth/google", json={"credential": "valid.token"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("not verified", self._get_error_message(res))

    def test_missing_google_client_id_configuration(self):
        settings.GOOGLE_CLIENT_ID = None

        res = self.client.post("/auth/google", json={"credential": "valid.token"})
        self.assertEqual(res.status_code, 500)
        self.assertEqual(self._get_error_message(res), "Google authentication is not configured.")

    @patch("app.api.auth.id_token.verify_oauth2_token")
    def test_concurrent_registration_race_handling(self, mock_verify):
        race_email = "race@example.com"
        mock_verify.return_value = self._mock_google_payload(email=race_email)

        # Simulate race condition: during first flush of user creation, an IntegrityError is raised
        # because a concurrent worker inserted the user first.
        original_add = self.db.add

        def simulate_race_add(instance):
            if isinstance(instance, User) and instance.email == race_email:
                # Insert the concurrent user directly in a separate session
                concurrent_user = User(
                    first_name="Concurrent",
                    last_name="Winner",
                    email=race_email,
                    hashed_password="concurrent_hash",
                    is_active=True,
                    is_verified=True,
                    role=RoleType.USER,
                )
                original_add(concurrent_user)
                self.db.commit()
                # Now the upcoming insert on this session will trigger IntegrityError on unique constraint
                raise IntegrityError("duplicate key value violates unique constraint", params=None, orig=None)
            original_add(instance)

        with patch.object(self.db, "add", side_effect=simulate_race_add):
            res = self.client.post("/auth/google", json={"credential": "valid.token"})
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertIn("access_token", data)
            token_payload = verify_access_token(data["access_token"])
            self.assertIsNotNone(token_payload)

            winner = self.db.query(User).filter(User.email == race_email).first()
            self.assertEqual(token_payload["sub"], str(winner.id))

    @patch("app.api.auth.provision_new_user_account")
    @patch("app.api.auth.id_token.verify_oauth2_token")
    def test_provisioning_failure_rolls_back_new_user(self, mock_verify, mock_provision):
        mock_verify.return_value = self._mock_google_payload(email="prov_fail@example.com")
        mock_provision.side_effect = RuntimeError("Wallet provisioning service failure")

        res = self.client.post("/auth/google", json={"credential": "valid.token"})
        self.assertEqual(res.status_code, 500)
        self.assertNotIn("access_token", res.json())

        # Verify new user was rolled back and is not in database
        user = self.db.query(User).filter(User.email == "prov_fail@example.com").first()
        self.assertIsNone(user)

    @patch("app.api.auth.id_token.verify_oauth2_token")
    def test_commit_failure_rolls_back_and_denies_token(self, mock_verify):
        mock_verify.return_value = self._mock_google_payload(email="commit_fail@example.com")

        # Mock commit failure during user creation
        with patch.object(self.db, "commit", side_effect=RuntimeError("Database commit failed")):
            res = self.client.post("/auth/google", json={"credential": "valid.token"})
            self.assertEqual(res.status_code, 500)
            self.assertNotIn("access_token", res.json())

        # Verify user was not left committed
        self.db.rollback()
        user = self.db.query(User).filter(User.email == "commit_fail@example.com").first()
        self.assertIsNone(user)

    @patch("app.api.auth.id_token.verify_oauth2_token")
    def test_integrity_error_without_existing_user_returns_500(self, mock_verify):
        mock_verify.return_value = self._mock_google_payload(email="unrelated_integrity@example.com")

        # Simulate IntegrityError where no concurrent user exists
        def fail_flush():
            raise IntegrityError("Unrelated constraint failure", params=None, orig=None)

        with patch.object(self.db, "flush", side_effect=fail_flush):
            res = self.client.post("/auth/google", json={"credential": "valid.token"})
            self.assertEqual(res.status_code, 500)
            self.assertIn("Database error during account creation", self._get_error_message(res))
            self.assertNotIn("access_token", res.json())

            user = self.db.query(User).filter(User.email == "unrelated_integrity@example.com").first()
            self.assertIsNone(user)

    @patch("app.api.auth.id_token.verify_oauth2_token")
    def test_inactive_race_winner_rejected(self, mock_verify):
        race_email = "inactive_race@example.com"
        mock_verify.return_value = self._mock_google_payload(email=race_email)

        original_add = self.db.add

        def simulate_race_add(instance):
            if isinstance(instance, User) and instance.email == race_email:
                concurrent_user = User(
                    first_name="Inactive",
                    last_name="Winner",
                    email=race_email,
                    hashed_password="concurrent_hash",
                    is_active=False,
                    is_verified=True,
                    role=RoleType.USER,
                )
                original_add(concurrent_user)
                self.db.commit()
                raise IntegrityError("duplicate key value violates unique constraint", params=None, orig=None)
            original_add(instance)

        with patch.object(self.db, "add", side_effect=simulate_race_add):
            res = self.client.post("/auth/google", json={"credential": "valid.token"})
            self.assertEqual(res.status_code, 403)
            self.assertIn("disabled", self._get_error_message(res).lower())
            self.assertNotIn("access_token", res.json())

    @patch("app.api.auth.provision_new_user_account")
    @patch("app.api.auth.id_token.verify_oauth2_token")
    def test_existing_user_not_reprovisioned(self, mock_verify, mock_provision):
        existing_email = "no_reprovision@example.com"
        mock_verify.return_value = self._mock_google_payload(email=existing_email)

        # Pre-create winner user with wallet already provisioned
        winner_user = User(
            id=505,
            first_name="PreExisting",
            last_name="Winner",
            email=existing_email,
            hashed_password="winner_hash",
            is_active=True,
            is_verified=True,
            role=RoleType.USER,
        )
        self.db.add(winner_user)
        self.db.commit()

        # Call /auth/google
        res = self.client.post("/auth/google", json={"credential": "valid.token"})
        self.assertEqual(res.status_code, 200)
        self.assertIn("access_token", res.json())

        # Ensure provision_new_user_account was NOT called
        mock_provision.assert_not_called()

    @patch("app.api.auth.id_token.verify_oauth2_token")
    def test_recovery_verification_commit_failure_rolls_back_and_denies_token(self, mock_verify):
        race_email = "recovery_fail@example.com"
        mock_verify.return_value = self._mock_google_payload(email=race_email)

        original_add = self.db.add
        original_commit = self.db.commit

        def simulate_race_add(instance):
            if isinstance(instance, User) and instance.email == race_email:
                # Concurrent user is unverified
                concurrent_user = User(
                    first_name="Unverified",
                    last_name="Winner",
                    email=race_email,
                    hashed_password="concurrent_hash",
                    is_active=True,
                    is_verified=False,
                    role=RoleType.USER,
                )
                original_add(concurrent_user)
                original_commit()
                raise IntegrityError("duplicate key value violates unique constraint", params=None, orig=None)
            original_add(instance)

        commit_call_count = [0]
        def fail_recovery_commit():
            commit_call_count[0] += 1
            if commit_call_count[0] == 1:
                # First commit in recovery when updating is_verified
                raise RuntimeError("Recovery verification commit failed")
            return original_commit()

        with patch.object(self.db, "add", side_effect=simulate_race_add):
            with patch.object(self.db, "commit", side_effect=fail_recovery_commit):
                res = self.client.post("/auth/google", json={"credential": "valid.token"})
                self.assertEqual(res.status_code, 500)
                self.assertNotIn("access_token", res.json())

    @patch("app.api.auth.id_token.verify_oauth2_token")
    def test_rate_limiter_active_on_endpoint(self, mock_verify):
        mock_verify.return_value = self._mock_google_payload()

        # Send 10 requests within window
        for i in range(10):
            res = self.client.post("/auth/google", json={"credential": f"valid.token.{i}"})
            self.assertEqual(res.status_code, 200)

        # 11th request hits rate limit (limit=10, window=60)
        res_blocked = self.client.post("/auth/google", json={"credential": "valid.token.11"})
        self.assertEqual(res_blocked.status_code, 429)
        self.assertIn("Too many requests", self._get_error_message(res_blocked))


if __name__ == "__main__":
    unittest.main()
