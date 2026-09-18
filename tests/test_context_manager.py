import unittest
from app.services.context_manager import ContextManager, get_tokenizer, estimate_tokens

class TestContextManager(unittest.TestCase):
    def setUp(self):
        # We set tight bounds for testing the truncation
        self.manager = ContextManager(max_input_tokens=100, max_output_tokens=50)
        self.system_prompt = "You are a helpful assistant."

    def test_estimate_tokens(self):
        # "Hello world" is typically 2 tokens
        tokens = estimate_tokens("Hello world")
        self.assertGreaterEqual(tokens, 1)

    def test_context_bounds_history(self):
        # Create a history where each message is around 20 tokens
        history = [
            {"role": "user", "content": "Message 1 " * 10},
            {"role": "assistant", "content": "Message 2 " * 10},
            {"role": "user", "content": "Message 3 " * 10},
            {"role": "assistant", "content": "Message 4 " * 10},
            {"role": "user", "content": "Message 5 " * 10},
        ]
        
        user_message = "Final message"
        
        result = self.manager.build_context(self.system_prompt, history, user_message)
        
        # It should truncate the older messages
        bounded = result["bounded_history"]
        
        # It definitely shouldn't contain the first message
        self.assertTrue(len(bounded) < len(history))
        
        # Output budget should be preserved
        self.assertEqual(result["available_output_budget"], 50)
        
        # Estimated input tokens should be <= 100
        self.assertLessEqual(result["estimated_input_tokens"], 100)

    def test_system_prompt_and_user_message_retained(self):
        # Even if history is empty, it returns the base tokens
        result = self.manager.build_context(self.system_prompt, [], "Hello")
        
        self.assertEqual(result["bounded_history"], [])
        self.assertGreater(result["estimated_input_tokens"], 0)

    def test_deterministic_tokenizer(self):
        # Test that encoding is deterministic
        tokenizer = get_tokenizer()
        enc1 = tokenizer.encode("deterministic test")
        enc2 = tokenizer.encode("deterministic test")
        self.assertEqual(enc1, enc2)

if __name__ == '__main__':
    unittest.main()
