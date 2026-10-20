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

        # Isolated SQLite in-memory database for testing
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(self.engine)

        self.db = self.SessionLocal()

        def override_get_db():
            try:
                yield self.db
            finally:
                pass

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

    def _get_error_message(self, response):
        data = response.json()
        detail = data.get("message") or data.get("detail")
        if isinstance(detail, list):
            return detail[0].get("msg")
        return detail

    # =========================================================================
    # 1. REGISTRATION TESTS (mode="register")
    # =========================================================================

    @patch("app.api.auth.send_welcome_email")
    @patch("app.api.auth.id_token.verify_oauth2_token")
    def test_new_user_registration_success(self, mock_verify, mock_send_welcome):
        mock_verify.return_value = self._mock_google_payload()

        res = self.client.post("/auth/google", json={"credential": "valid.mock.token", "mode": "register"})
        self.assertEqual(res.status_code, 200)

        data = res.json()
        self.assertIn("access_token", data)
        self.assertEqual(data["token_type"], "bearer")

        token_payload = verify_access_token(data["access_token"])
        self.assertIsNotNone(token_payload)

        created_user = self.db.query(User).filter(User.email == "googleuser@example.com").first()
        self.assertIsNotNone(created_user)
        self.assertEqual(str(created_user.id), token_payload["sub"])
        self.assertEqual(created_user.first_name, "Google")
        self.assertEqual(created_user.last_name, "Tester")
        self.assertEqual(created_user.google_sub, "google-user-id-999")
        self.assertTrue(created_user.is_verified)
        self.assertTrue(created_user.is_active)
        self.assertEqual(created_user.role, RoleType.USER)

        wallet = self.db.query(Wallet).filter(Wallet.user_id == created_user.id).first()
        self.assertIsNotNone(wallet)
        self.assertGreater(wallet.subscription_balance, 0)

        subscription = self.db.query(Subscription).filter(Subscription.user_id == created_user.id).first()
        self.assertIsNotNone(subscription)
        self.assertEqual(subscription.plan_id, "free")

        mock_send_welcome.assert_called_once_with("googleuser@example.com")

    @patch("app.api.auth.id_token.verify_oauth2_token")
    def test_register_when_account_already_exists_fails_409(self, mock_verify):
        mock_verify.return_value = self._mock_google_payload(email="existing@example.com", sub="google-sub-111")

        # First registration succeeds
        res1 = self.client.post("/auth/google", json={"credential": "token.1", "mode": "register"})
        self.assertEqual(res1.status_code, 200)

        # Attempt to register again with same Google account
        res2 = self.client.post("/auth/google", json={"credential": "token.2", "mode": "register"})
        self.assertEqual(res2.status_code, 409)
        self.assertEqual(self._get_error_message(res2), "An account with this email already exists. Please sign in instead.")

    @patch("app.api.auth.id_token.verify_oauth2_token")
    def test_name_parsing_fallbacks(self, mock_verify):
        mock_verify.return_value = self._mock_google_payload(
            email="fullname@example.com",
            sub="google-sub-222",
            given_name="",
            family_name="",
            name="Jane Doe",
        )
        res = self.client.post("/auth/google", json={"credential": "valid.mock.token", "mode": "register"})
        self.assertEqual(res.status_code, 200)
        user = self.db.query(User).filter(User.email == "fullname@example.com").first()
        self.assertIsNotNone(user)
        self.assertEqual(user.first_name, "Jane")
        self.assertEqual(user.last_name, "Doe")

        mock_verify.return_value = self._mock_google_payload(
            email="nonameuser@example.com",
            sub="google-sub-333",
            given_name="",
            family_name="",
            name="",
        )
        res = self.client.post("/auth/google", json={"credential": "valid.mock.token", "mode": "register"})
        self.assertEqual(res.status_code, 200)
        user2 = self.db.query(User).filter(User.email == "nonameuser@example.com").first()
        self.assertIsNotNone(user2)
        self.assertEqual(user2.first_name, "nonameuser")
        self.assertEqual(user2.last_name, "")

    # =========================================================================
    # 2. SIGN-IN TESTS (mode="login")
    # =========================================================================

    @patch("app.api.auth.id_token.verify_oauth2_token")
    def test_login_unknown_account_returns_404_and_does_not_create(self, mock_verify):
        mock_verify.return_value = self._mock_google_payload(email="unknown@example.com", sub="unknown-sub")

        res = self.client.post("/auth/google", json={"credential": "valid.token", "mode": "login"})
        self.assertEqual(res.status_code, 404)
        self.assertEqual(self._get_error_message(res), "No Bazzix account found for this Google email. Please create an account first.")

        # Confirm no account was created in DB
        user = self.db.query(User).filter(User.email == "unknown@example.com").first()
        self.assertIsNone(user)

    @patch("app.api.auth.id_token.verify_oauth2_token")
    def test_login_existing_google_account_succeeds(self, mock_verify):
        mock_verify.return_value = self._mock_google_payload(email="returning@example.com", sub="returning-sub-444")

        # Pre-create Google user
        res_reg = self.client.post("/auth/google", json={"credential": "reg.token", "mode": "register"})
        self.assertEqual(res_reg.status_code, 200)

        # Login
        res_login = self.client.post("/auth/google", json={"credential": "login.token", "mode": "login"})
        self.assertEqual(res_login.status_code, 200)
        data = res_login.json()
        self.assertIn("access_token", data)

        # Ensure no duplicate wallets created
        user = self.db.query(User).filter(User.email == "returning@example.com").first()
        wallets = self.db.query(Wallet).filter(Wallet.user_id == user.id).all()
        self.assertEqual(len(wallets), 1)

    @patch("app.api.auth.id_token.verify_oauth2_token")
    def test_login_password_account_fails_409_linking_required(self, mock_verify):
        # Create an account via email/password (google_sub is None)
        pw_user = User(
            first_name="Password",
            last_name="User",
            email="pw_user@example.com",
            hashed_password="hashed_pw_argon2",
            google_sub=None,
            is_active=True,
            is_verified=True,
            role=RoleType.USER,
        )
        self.db.add(pw_user)
        self.db.commit()

        mock_verify.return_value = self._mock_google_payload(email="pw_user@example.com", sub="some-google-sub")

        # Attempt to sign in with Google
        res = self.client.post("/auth/google", json={"credential": "valid.token", "mode": "login"})
        self.assertEqual(res.status_code, 409)
        self.assertEqual(
            self._get_error_message(res),
            "This account was registered with an email and password. Please sign in with your email and password.",
        )

        # Password hash must remain untouched
        self.db.expire_all()
        user_after = self.db.query(User).filter(User.email == "pw_user@example.com").first()
        self.assertEqual(user_after.hashed_password, "hashed_pw_argon2")

    @patch("app.api.auth.id_token.verify_oauth2_token")
    def test_login_google_sub_mismatch_fails_401(self, mock_verify):
        google_user = User(
            first_name="Google",
            last_name="User",
            email="google_mismatch@example.com",
            hashed_password="some_random_hash",
            google_sub="original-google-sub-555",
            is_active=True,
            is_verified=True,
            role=RoleType.USER,
        )
        self.db.add(google_user)
        self.db.commit()

        # Token comes with same email but DIFFERENT sub
        mock_verify.return_value = self._mock_google_payload(
            email="google_mismatch@example.com",
            sub="different-attacker-sub-999",
        )

        res = self.client.post("/auth/google", json={"credential": "valid.token", "mode": "login"})
        self.assertEqual(res.status_code, 401)
        self.assertEqual(self._get_error_message(res), "Google account identity mismatch.")

    @patch("app.api.auth.id_token.verify_oauth2_token")
    def test_inactive_user_rejected(self, mock_verify):
        disabled_user = User(
            first_name="Disabled",
            last_name="User",
            email="disabled@example.com",
            hashed_password="some_random_hash",
            google_sub="disabled-sub-666",
            is_active=False,
            is_verified=True,
            role=RoleType.USER,
        )
        self.db.add(disabled_user)
        self.db.commit()

        mock_verify.return_value = self._mock_google_payload(
            email="disabled@example.com",
            sub="disabled-sub-666",
        )

        res = self.client.post("/auth/google", json={"credential": "valid.mock.token", "mode": "login"})
        self.assertEqual(res.status_code, 403)
        self.assertEqual(self._get_error_message(res), "Account is disabled. Please contact support.")

    # =========================================================================
    # 3. TOKEN VALIDATION & SECURITY TESTS
    # =========================================================================

    def test_missing_and_blank_credentials(self):
        res1 = self.client.post("/auth/google", json={"credential": ""})
        self.assertEqual(res1.status_code, 422)

        res2 = self.client.post("/auth/google", json={"credential": "   "})
        self.assertEqual(res2.status_code, 422)

    @patch("app.api.auth.id_token.verify_oauth2_token")
    def test_invalid_google_signature_fails_401(self, mock_verify):
        mock_verify.side_effect = ValueError("Invalid token signature")
        res = self.client.post("/auth/google", json={"credential": "invalid.signature.token"})
        self.assertEqual(res.status_code, 401)
        self.assertEqual(self._get_error_message(res), "Invalid Google credential.")

    @patch("app.api.auth.id_token.verify_oauth2_token")
    def test_expired_google_token_fails_401(self, mock_verify):
        mock_verify.side_effect = GoogleAuthError("Token has expired")
        res = self.client.post("/auth/google", json={"credential": "expired.token"})
        self.assertEqual(res.status_code, 401)
        self.assertEqual(self._get_error_message(res), "Invalid Google credential.")

    @patch("app.api.auth.id_token.verify_oauth2_token")
    def test_untrusted_issuer_fails_401(self, mock_verify):
        mock_verify.return_value = self._mock_google_payload(iss="https://malicious.issuer.org")
        res = self.client.post("/auth/google", json={"credential": "fake.iss.token"})
        self.assertEqual(res.status_code, 401)
        self.assertEqual(self._get_error_message(res), "Invalid Google credential.")

    @patch("app.api.auth.id_token.verify_oauth2_token")
    def test_audience_mismatch_fails_401(self, mock_verify):
        mock_verify.return_value = self._mock_google_payload(aud="attacker-client-id.apps.googleusercontent.com")
        res = self.client.post("/auth/google", json={"credential": "wrong.aud.token"})
        self.assertEqual(res.status_code, 401)
        self.assertEqual(self._get_error_message(res), "Invalid Google credential.")

    @patch("app.api.auth.id_token.verify_oauth2_token")
    def test_missing_or_unverified_email_fails(self, mock_verify):
        mock_verify.return_value = self._mock_google_payload(email=None)
        res1 = self.client.post("/auth/google", json={"credential": "valid.token"})
        self.assertEqual(res1.status_code, 400)
        self.assertEqual(self._get_error_message(res1), "Google account email is missing.")

        mock_verify.return_value = self._mock_google_payload(email_verified=False)
        res2 = self.client.post("/auth/google", json={"credential": "valid.token"})
        self.assertEqual(res2.status_code, 400)
        self.assertEqual(self._get_error_message(res2), "Google account email is not verified.")

    def test_missing_google_client_id_configuration(self):
        settings.GOOGLE_CLIENT_ID = None
        res = self.client.post("/auth/google", json={"credential": "valid.token"})
        self.assertEqual(res.status_code, 500)
        self.assertEqual(self._get_error_message(res), "Google authentication is not configured.")

    # =========================================================================
    # 4. CONCURRENCY & TRANSACTION INTEGRITY TESTS
    # =========================================================================

    @patch("app.api.auth.id_token.verify_oauth2_token")
    def test_concurrent_registration_race_handling(self, mock_verify):
        race_email = "race@example.com"
        race_sub = "race-sub-777"
        mock_verify.return_value = self._mock_google_payload(email=race_email, sub=race_sub)

        original_add = self.db.add

        def simulate_race_add(instance):
            if isinstance(instance, User) and instance.email == race_email:
                concurrent_user = User(
                    first_name="Concurrent",
                    last_name="Winner",
                    email=race_email,
                    hashed_password="concurrent_hash",
                    google_sub=race_sub,
                    is_active=True,
                    is_verified=True,
                    role=RoleType.USER,
                )
                original_add(concurrent_user)
                self.db.commit()
                raise IntegrityError("duplicate key value violates unique constraint", params=None, orig=None)
            original_add(instance)

        with patch.object(self.db, "add", side_effect=simulate_race_add):
            res = self.client.post("/auth/google", json={"credential": "valid.token", "mode": "register"})
            # In register mode, concurrent creation means the account was already created!
            self.assertEqual(res.status_code, 409)
            self.assertEqual(self._get_error_message(res), "An account with this email already exists. Please sign in instead.")

    @patch("app.api.auth.id_token.verify_oauth2_token")
    def test_provisioning_failure_rolls_back_new_user(self, mock_verify):
        mock_verify.return_value = self._mock_google_payload(email="prov_fail@example.com", sub="prov-fail-sub")

        with patch("app.api.auth.provision_new_user_account", side_effect=RuntimeError("Wallet service down")):
            res = self.client.post("/auth/google", json={"credential": "valid.token", "mode": "register"})
            self.assertEqual(res.status_code, 500)

        # Confirm user was rolled back
        user = self.db.query(User).filter(User.email == "prov_fail@example.com").first()
        self.assertIsNone(user)

    @patch("app.api.auth.id_token.verify_oauth2_token")
    def test_commit_failure_rolls_back_and_denies_token(self, mock_verify):
        mock_verify.return_value = self._mock_google_payload(email="commit_fail@example.com", sub="commit-fail-sub")

        with patch.object(self.db, "commit", side_effect=RuntimeError("Database commit failed")):
            res = self.client.post("/auth/google", json={"credential": "valid.token", "mode": "register"})
            self.assertEqual(res.status_code, 500)

        user = self.db.query(User).filter(User.email == "commit_fail@example.com").first()
        self.assertIsNone(user)

    @patch("app.api.auth.id_token.verify_oauth2_token")
    def test_rate_limiter_active_on_endpoint(self, mock_verify):
        mock_verify.return_value = self._mock_google_payload(email="rl_user@example.com", sub="rl-sub")

        for i in range(10):
            res = self.client.post("/auth/google", json={"credential": f"valid.token.{i}", "mode": "register"})
            # First one might succeed or fail, but shouldn't be 429
            self.assertNotEqual(res.status_code, 429)

        # 11th request triggers rate limit (limit=10, window=60)
        res_blocked = self.client.post("/auth/google", json={"credential": "valid.token.11", "mode": "register"})
        self.assertEqual(res_blocked.status_code, 429)

    @patch("app.api.auth.id_token.verify_oauth2_token")
    def test_default_mode_is_login(self, mock_verify):
        # Calling without mode defaults to login -> 404 for unknown user
        mock_verify.return_value = self._mock_google_payload(email="default_mode@example.com", sub="sub-default")
        res = self.client.post("/auth/google", json={"credential": "valid.token"})
        self.assertEqual(res.status_code, 404)
        self.assertEqual(self._get_error_message(res), "No Bazzix account found for this Google email. Please create an account first.")

    def test_invalid_mode_fails_422(self):
        res = self.client.post("/auth/google", json={"credential": "valid.token", "mode": "invalid_mode"})
        self.assertEqual(res.status_code, 422)

    @patch("app.api.auth.id_token.verify_oauth2_token")
    def test_unverified_existing_google_account_becomes_verified_on_login(self, mock_verify):
        unverified_user = User(
            first_name="Unverified",
            last_name="GoogleUser",
            email="unverified_google@example.com",
            hashed_password="some_random_hash",
            google_sub="unverified-sub-888",
            is_active=True,
            is_verified=False,
            role=RoleType.USER,
        )
        self.db.add(unverified_user)
        self.db.commit()

        mock_verify.return_value = self._mock_google_payload(
            email="unverified_google@example.com",
            sub="unverified-sub-888",
        )

        res = self.client.post("/auth/google", json={"credential": "valid.token", "mode": "login"})
        self.assertEqual(res.status_code, 200)

        self.db.expire_all()
        refreshed = self.db.query(User).filter(User.id == unverified_user.id).first()
        self.assertTrue(refreshed.is_verified)


if __name__ == "__main__":
    unittest.main()
