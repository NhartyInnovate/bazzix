import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.crud.user import create_user
from app.schemas.user import UserCreate
from app.db.database import SessionLocal, Base, engine
from sqlalchemy import text

class TestPasswordResetConfig(unittest.TestCase):
    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        # Clean up users to avoid unique constraint errors
        self.db.execute(text("DELETE FROM users"))
        self.db.commit()
        
        self.test_email = "reset_test@example.com"
        create_user(self.db, UserCreate(
            first_name="Test",
            last_name="User",
            email=self.test_email,
            password="strongpassword123!"
        ))
        self.client = TestClient(app)
        
        # Clear global rate limit records to prevent 429 when running entire suite
        from app.core.rate_limit import rate_limit_records
        rate_limit_records.clear()

    def tearDown(self):
        self.db.execute(text("DELETE FROM users"))
        self.db.commit()
        self.db.close()

    def test_production_missing_resend_key_fails(self):
        import io
        import logging
        
        log_capture = io.StringIO()
        handler = logging.StreamHandler(log_capture)
        logger = logging.getLogger('app.api.auth')
        logger.addHandler(handler)

        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout, \
             patch('sys.stderr', new_callable=io.StringIO) as mock_stderr:
             
            with patch.object(settings, 'ENVIRONMENT', 'production'):
                with patch.object(settings, 'RESEND_API_KEY', None):
                    response = self.client.post("/auth/forgot-password", json={"email": self.test_email})
                    self.assertEqual(response.status_code, 500)
                    self.assertIn("server configuration error", response.json()["message"])
                    
            stdout_output = mock_stdout.getvalue()
            stderr_output = mock_stderr.getvalue()
            log_output = log_capture.getvalue()
            
            self.assertNotIn("token=", stdout_output)
            self.assertNotIn("reset-password", stdout_output)
            self.assertNotIn("token=", stderr_output)
            self.assertNotIn("reset-password", stderr_output)
            self.assertNotIn("token=", log_output)
            self.assertNotIn("reset-password", log_output)
            
        logger.removeHandler(handler)

    @patch('app.api.auth.send_reset_email')
    def test_development_missing_resend_key_succeeds(self, mock_send):
        with patch.object(settings, 'ENVIRONMENT', 'development'):
            with patch.object(settings, 'RESEND_API_KEY', None):
                response = self.client.post("/auth/forgot-password", json={"email": self.test_email})
                self.assertEqual(response.status_code, 200)
                self.assertIn("reset link shortly", response.json()["message"])
                mock_send.assert_called_once()

    @patch('app.api.auth.resend.Emails.send')
    def test_production_with_resend_key_succeeds(self, mock_resend_send):
        with patch.object(settings, 'ENVIRONMENT', 'production'):
            with patch.object(settings, 'RESEND_API_KEY', 're_testkey'):
                response = self.client.post("/auth/forgot-password", json={"email": self.test_email})
                self.assertEqual(response.status_code, 200)
                self.assertIn("reset link shortly", response.json()["message"])
                mock_resend_send.assert_called_once()

if __name__ == '__main__':
    unittest.main()
