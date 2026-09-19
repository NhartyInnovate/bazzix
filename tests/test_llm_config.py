import unittest
import importlib
from unittest.mock import patch
from app.core.config import settings

class TestLLMConfig(unittest.TestCase):
    def tearDown(self):
        # Restore original module state for other tests
        import app.services.llm as llm
        importlib.reload(llm)

    def test_production_missing_key_fails(self):
        with patch.object(settings, 'OPENAI_API_KEY', None):
            with patch.object(settings, 'ENVIRONMENT', 'production'):
                import app.services.llm as llm
                with self.assertRaises(ValueError) as context:
                    importlib.reload(llm)
                self.assertIn("Production cannot run in mock mode", str(context.exception))

    def test_development_missing_key_mock_mode(self):
        with patch.object(settings, 'OPENAI_API_KEY', None):
            with patch.object(settings, 'ENVIRONMENT', 'development'):
                import app.services.llm as llm
                importlib.reload(llm)
                self.assertIsNone(llm.client)

    def test_production_with_key_succeeds(self):
        with patch.object(settings, 'OPENAI_API_KEY', 'sk-test-key'):
            with patch.object(settings, 'ENVIRONMENT', 'production'):
                import app.services.llm as llm
                importlib.reload(llm)
                self.assertIsNotNone(llm.client)
                self.assertEqual(llm.client.api_key, 'sk-test-key')

if __name__ == '__main__':
    unittest.main()
