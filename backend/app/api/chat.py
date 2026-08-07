from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
import json
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.core.dependencies import get_current_user

from app.schemas.message import (
    ChatRequest,
    ChatResponse,
)

from app.services.chat import process_chat, process_chat_stream
from app.core.rate_limit import rate_limiter

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


@router.post("", response_model=ChatResponse, dependencies=[Depends(rate_limiter(limit=20, window=60))])
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):

    try:

        response = await process_chat(
            db,
            current_user.id,
            request.conversation_id,
            request.message,
        )

        return ChatResponse(
            response=response,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )

    except RuntimeError as e:
        import traceback

        traceback.print_exc()
        print(f"\nFULL ERROR: {repr(e)}\n")

        raise HTTPException(
            status_code=503,
            detail=str(e)
        )


@router.post("/stream", dependencies=[Depends(rate_limiter(limit=20, window=60))])
async def chat_stream(
    request: ChatRequest,
    req_obj: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        generator = await process_chat_stream(
            db,
            current_user.id,
            request.conversation_id,
            request.message,
        )

        async def sse_event_generator():
            try:
                async for chunk in generator:
                    if await req_obj.is_disconnected():
                        print("Client disconnected. Aborting response stream.")
                        break
                    yield f"data: {json.dumps({'content': chunk})}\n\n"
            except Exception as e:
                print(f"Error yielding stream chunks: {e}")
                yield f"event: error\ndata: {json.dumps({'detail': str(e)})}\n\n"

        return StreamingResponse(sse_event_generator(), media_type="text/event-stream")

    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )

    except RuntimeError as e:
        import traceback

        traceback.print_exc()
        print(f"\nFULL ERROR: {repr(e)}\n")

        raise HTTPException(
            status_code=503,
            detail=str(e)
        )