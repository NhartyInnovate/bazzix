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

    from app.services.context_manager import ContextManager
    context_manager = ContextManager()
    
    raw_history = []
    for msg in history[:-1]:
        raw_history.append({"role": msg.role, "content": msg.content})
        
    context_data = context_manager.build_context(SYSTEM_PROMPT, raw_history, user_message)
    contents = context_data["bounded_history"] + [{"role": "user", "content": user_message}]

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
    client_request_id: str,
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

    from app.services.ai_request import create_ai_request_log, finalize_ai_request_log
    from app.models.ai_request import RequestStatus, UsageSource
    ai_request = create_ai_request_log(db, client_request_id, user_id, conversation_id)

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

    from app.services.context_manager import ContextManager
    from app.services.pricing import calculate_cost
    from app.services.credit_manager import reserve_credits, finalize_and_settle_credits
    from app.core.config import settings
    
    context_manager = ContextManager()
    
    # Map history to dicts for context manager
    raw_history = []
    for msg in history[:-1]:
        raw_history.append({"role": msg.role, "content": msg.content})
        
    context_data = context_manager.build_context(SYSTEM_PROMPT, raw_history, user_message)
    contents = context_data["bounded_history"] + [{"role": "user", "content": user_message}]
    
    # Calculate max required cost
    max_cost_result = calculate_cost(
        provider="openai",
        model=settings.OPENAI_MODEL,
        prompt_tokens=context_data["estimated_input_tokens"],
        completion_tokens=context_data["available_output_budget"],
        cached_tokens=0 # Safest assumption: nothing is cached
    )
    
    try:
        # Attempt to reserve credits. This holds a row lock momentarily and commits.
        reserved_amount = reserve_credits(
            db=db,
            user_id=user_id,
            request_id=ai_request.id,
            max_cost=max_cost_result.bazzix_credits
        )
    except Exception as e:
        # If reservation fails (e.g. InsufficientCreditsError), the request cannot proceed.
        # Mark the AIRequestLog as FAILED so it does not remain PENDING forever.
        finalize_ai_request_log(db, ai_request, status=RequestStatus.FAILED)
        raise e
    
    async def sse_generator():
        full_response = ""
        usage_data = None
        is_completed = False
        disconnect_interrupted = False
        provider_error = False
        try:
            async for chunk in structured_chat_stream(
                contents, 
                SYSTEM_PROMPT, 
                max_completion_tokens=context_data["available_output_budget"]
            ):
                if isinstance(chunk, dict):
                    if chunk.get("type") == "metadata":
                        ai_request.provider_request_id = chunk.get("provider_request_id")
                        db.add(ai_request)
                        db.commit()
                    elif chunk.get("type") == "content":
                        text = chunk.get("content", "")
                        full_response += text
                        yield text
                    elif chunk.get("type") == "usage":
                        usage_data = chunk
                else:
                    full_response += chunk
                    yield chunk
            
            save_message(
                db,
                conversation_id,
                "assistant",
                full_response,
            )
            is_completed = True
        except GeneratorExit:
            print("Stream interrupted by client disconnect.")
            disconnect_interrupted = True
            raise
        except Exception as e:
            print(f"Error during streaming: {e}")
            provider_error = True
            raise e
        finally:
            # We must settle the reservation regardless of how the stream ended.
            req_id = None
            prompt_t = None
            comp_t = None
            cached_t = None
            src = None
            
            if usage_data:
                prompt_t = usage_data.get("prompt_tokens")
                comp_t = usage_data.get("completion_tokens")
                cached_t = usage_data.get("cached_tokens")
                req_id = usage_data.get("provider_request_id")
                src = UsageSource.PROVIDER
                
            if is_completed:
                finalize_and_settle_credits(
                    db, ai_request,
                    status=RequestStatus.COMPLETED,
                    provider_request_id=req_id,
                    prompt_tokens=prompt_t,
                    completion_tokens=comp_t,
                    cached_tokens=cached_t,
                    usage_source=src
                )
            elif disconnect_interrupted:
                if full_response.strip():
                    save_message(db, conversation_id, "assistant", full_response)
                    finalize_and_settle_credits(
                        db, ai_request,
                        status=RequestStatus.PARTIAL,
                        provider_request_id=req_id,
                        prompt_tokens=prompt_t,
                        completion_tokens=comp_t,
                        cached_tokens=cached_t,
                        usage_source=src
                    )
                else:
                    finalize_and_settle_credits(
                        db, ai_request,
                        status=RequestStatus.FAILED,
                        provider_request_id=req_id,
                        prompt_tokens=prompt_t,
                        completion_tokens=comp_t,
                        cached_tokens=cached_t,
                        usage_source=src
                    )
            elif provider_error:
                if full_response.strip():
                    save_message(db, conversation_id, "assistant", full_response)
                # Explicitly mark FAILED if provider API threw an exception, even if partial text arrived.
                finalize_and_settle_credits(
                    db, ai_request,
                    status=RequestStatus.FAILED,
                    provider_request_id=req_id,
                    prompt_tokens=prompt_t,
                    completion_tokens=comp_t,
                    cached_tokens=cached_t,
                    usage_source=src
                )
            else:
                # Catch-all
                finalize_and_settle_credits(
                    db, ai_request,
                    status=RequestStatus.FAILED,
                    provider_request_id=req_id,
                    prompt_tokens=prompt_t,
                    completion_tokens=comp_t,
                    cached_tokens=cached_t,
                    usage_source=src
                )

    return sse_generator()