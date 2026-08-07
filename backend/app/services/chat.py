from sqlalchemy.orm import Session

from app.crud.conversation import (
    get_conversation,
    update_conversation_title,
)

from app.crud.message import (
    save_message,
    get_conversation_messages,
)

from app.services.ai import structured_chat, structured_chat_stream
from app.services.prompt_builder import build_structured_contents, SYSTEM_PROMPT
from app.services.title_generator import generate_title
import time



async def process_chat(
    db: Session,
    user_id: int,
    conversation_id: int,
    user_message: str,
):
    request_start = time.perf_counter()

    conversation = get_conversation(
        db,
        conversation_id,
    )

    if (
        conversation is None
        or conversation.user_id != user_id
    ):
        raise ValueError("Conversation not found")

    save_message(
        db,
        conversation_id,
        "user",
        user_message,
    )

    history = get_conversation_messages(
        db,
        conversation_id,
    )

    if len(history) == 1:
        title = await generate_title(user_message)

        update_conversation_title(
            db,
            conversation,
            title,
        )

    contents = build_structured_contents(
        history[:-1],
        user_message,
    )

    gemini_start = time.perf_counter()

    ai_response = await structured_chat(contents, SYSTEM_PROMPT)

    print(
        f"Gemini took {time.perf_counter() - gemini_start:.2f}s"
    )

    save_message(
        db,
        conversation_id,
        "assistant",
        ai_response,
    )

    print(
        f"Total request took {time.perf_counter() - request_start:.2f}s"
    )

    return ai_response


async def process_chat_stream(
    db: Session,
    user_id: int,
    conversation_id: int,
    user_message: str,
):
    conversation = get_conversation(
        db,
        conversation_id,
    )

    if (
        conversation is None
        or conversation.user_id != user_id
    ):
        raise ValueError("Conversation not found")

    save_message(
        db,
        conversation_id,
        "user",
        user_message,
    )

    history = get_conversation_messages(
        db,
        conversation_id,
    )

    if len(history) == 1:
        title = await generate_title(user_message)

        update_conversation_title(
            db,
            conversation,
            title,
        )

    contents = build_structured_contents(
        history[:-1],
        user_message,
    )

    async def sse_generator():
        full_response = ""
        try:
            async for chunk in structured_chat_stream(contents, SYSTEM_PROMPT):
                full_response += chunk
                yield chunk
            
            save_message(
                db,
                conversation_id,
                "assistant",
                full_response,
            )
        except Exception as e:
            print(f"Error during streaming: {e}")
            raise e

    return sse_generator()