import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

# Fallback fake encoding for environments where tiktoken cannot build (e.g. missing Rust)
class DummyEncoding:
    def encode(self, text: str):
        # Extremely rough estimation fallback
        return [1] * (len(text) // 4)

try:
    import tiktoken
    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False
    logger.warning("tiktoken not installed. Using dummy token estimation.")

def get_tokenizer():
    if not HAS_TIKTOKEN:
        return DummyEncoding()
    try:
        # We try to load the exact tokenizer for the configured model
        return tiktoken.encoding_for_model(settings.OPENAI_MODEL)
    except KeyError:
        # Fallback to the latest encoding if the model is too new for this tiktoken version
        # o200k_base is used for gpt-4o and gpt-4o-mini
        try:
            return tiktoken.get_encoding("o200k_base")
        except Exception:
            return tiktoken.get_encoding("cl100k_base")

def estimate_tokens(text: str) -> int:
    tokenizer = get_tokenizer()
    return len(tokenizer.encode(text))

def estimate_message_tokens(message: dict) -> int:
    """
    Estimates tokens for a given message dictionary.
    Includes overhead for the message framing (<|im_start|>, role, <|im_end|>).
    """
    # 3 tokens overhead per message (role framing)
    tokens = 3
    for key, value in message.items():
        tokens += estimate_tokens(str(value))
    return tokens

class ContextManager:
    """
    Responsible for bounding the conversation history to fit within a configured
    token budget. It estimates tokens but does NOT act as the authoritative provider bill.
    """
    def __init__(self, max_input_tokens: int = None, max_output_tokens: int = None):
        self.max_input_tokens = max_input_tokens or settings.MAX_INPUT_TOKENS
        self.max_output_tokens = max_output_tokens or settings.MAX_OUTPUT_TOKENS

    def build_context(self, system_prompt: str, history: list[dict], user_message: str) -> dict:
        system_msg = {"role": "system", "content": system_prompt}
        user_msg = {"role": "user", "content": user_message}
        
        # Base tokens (system prompt + user message + overall request overhead)
        base_tokens = 3 + estimate_message_tokens(system_msg) + estimate_message_tokens(user_msg)
        
        final_history = []
        current_tokens = base_tokens
        
        # Traverse history backwards to retain the most recent context
        for msg in reversed(history):
            msg_tokens = estimate_message_tokens(msg)
            # If adding this message exceeds our input budget, we drop it and older messages
            if current_tokens + msg_tokens > self.max_input_tokens:
                break
            current_tokens += msg_tokens
            final_history.insert(0, msg)
            
        return {
            "estimated_input_tokens": current_tokens,
            "available_output_budget": max(0, self.max_output_tokens),
            "bounded_history": final_history
        }
