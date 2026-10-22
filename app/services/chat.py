from sqlalchemy.orm import Session

from app.crud.conversation import (
    get_conversation,
    update_conversation_title,
)

from app.crud.message import (
    save_message,
    get_conversation_messages,
    get_conversation_messages as _default_get_conversation_messages,
    iter_conversation_messages_newest_first,
)

from app.services.ai import structured_chat, structured_chat_stream
from app.services.prompt_builder import build_structured_contents, SYSTEM_PROMPT
from app.services.title_generator import generate_title
import time



import uuid


def _load_bounded_chat_context(
    db: Session,
    conversation_id: int,
    user_message: str,
    system_prompt: str = SYSTEM_PROMPT,
    context_manager=None,
    batch_size: int = 200,
) -> tuple[bool, dict]:
    if get_conversation_messages is not _default_get_conversation_messages:
        history = get_conversation_messages(
            db,
            conversation_id,
        )
        newest_first_iter = iter(reversed(history))
    else:
        newest_first_iter = iter_conversation_messages_newest_first(
            db=db,
            conversation_id=conversation_id,
            batch_size=batch_size,
        )

    first = next(newest_first_iter, None)
    second = next(newest_first_iter, None)
    is_first_message = first is not None and second is None

    if context_manager is None:
        from app.services.context_manager import ContextManager
        context_manager = ContextManager()

    def _prior_messages_newest_first():
        if second is not None:
            yield {"role": second.role, "content": second.content}
        for msg in newest_first_iter:
            yield {"role": msg.role, "content": msg.content}

    context_data = context_manager.build_context_from_newest_first(
        system_prompt=system_prompt,
        newest_first_messages=_prior_messages_newest_first(),
        user_message=user_message,
    )
    return is_first_message, context_data


async def process_chat(
    db: Session,
    user_id: int,
    conversation_id: int,
    user_message: str,
    client_request_id: str | None = None,
):
    if not client_request_id:
        client_request_id = str(uuid.uuid4())

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

    from app.services.context_manager import ContextManager
    from app.services.pricing import calculate_cost
    from app.services.credit_manager import reserve_credits, finalize_and_settle_credits
    from app.core.config import settings

    context_manager = ContextManager()
    is_first_message, context_data = _load_bounded_chat_context(
        db=db,
        conversation_id=conversation_id,
        user_message=user_message,
        system_prompt=SYSTEM_PROMPT,
        context_manager=context_manager,
    )

    if is_first_message:
        from app.services.title_generator import dispatch_background_title
        dispatch_background_title(conversation_id, user_message)

    contents = context_data["bounded_history"] + [{"role": "user", "content": user_message}]

    # Calculate max required cost
    max_cost_result = calculate_cost(
        provider="openai",
        model=settings.OPENAI_MODEL,
        prompt_tokens=context_data["estimated_input_tokens"],
        completion_tokens=context_data["available_output_budget"],
        cached_tokens=0  # Safest assumption: nothing is cached
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
        # If reservation fails (e.g. InsufficientCreditsError), request cannot proceed.
        # Mark AIRequestLog as FAILED so it does not remain PENDING forever.
        finalize_ai_request_log(db, ai_request, status=RequestStatus.FAILED)
        raise e

    ai_response = None
    usage_data = None
    provider_error = False

    try:
        ai_response, usage_data = await structured_chat(
            contents,
            SYSTEM_PROMPT,
            return_usage=True
        )

        save_message(
            db,
            conversation_id,
            "assistant",
            ai_response,
        )
    except Exception as e:
        provider_error = True
        raise e
    finally:
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

        if not provider_error and ai_response is not None:
            finalize_and_settle_credits(
                db, ai_request,
                status=RequestStatus.COMPLETED,
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

    from app.services.context_manager import ContextManager
    from app.services.pricing import calculate_cost
    from app.services.credit_manager import reserve_credits, finalize_and_settle_credits
    from app.core.config import settings

    context_manager = ContextManager()
    is_first_message, context_data = _load_bounded_chat_context(
        db=db,
        conversation_id=conversation_id,
        user_message=user_message,
        system_prompt=SYSTEM_PROMPT,
        context_manager=context_manager,
    )

    if is_first_message:
        from app.services.title_generator import dispatch_background_title
        dispatch_background_title(conversation_id, user_message)

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