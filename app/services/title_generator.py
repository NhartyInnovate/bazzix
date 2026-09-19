from app.services.llm import generate_response


async def generate_title(first_message: str) -> str:
    prompt = f"""
Generate a very short conversation title.

Rules:
- Maximum 5 words.
- No quotation marks.
- No punctuation.
- Return ONLY the title.

User Message:
{first_message}
"""

    title = await generate_response(prompt)

    print("=" * 50)

    print("GENERATED TITLE:", repr(title))

    print("=" * 50)

    return title.strip()
import asyncio
from app.db.database import SessionLocal
from app.crud.conversation import get_conversation, update_conversation_title

_bg_tasks = set()

async def _background_generate_title(conversation_id: int, user_message: str):
    try:
        title = await generate_title(user_message)
        db = SessionLocal()
        try:
            conversation = get_conversation(db, conversation_id)
            if conversation:
                update_conversation_title(db, conversation, title)
        finally:
            db.close()
    except Exception as e:
        print(f"Error generating title for conversation {conversation_id}: {e}")

def dispatch_background_title(conversation_id: int, user_message: str):
    task = asyncio.create_task(_background_generate_title(conversation_id, user_message))
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)
