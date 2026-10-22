from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.dependencies import get_db
from app.schemas.conversation import (
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
    ConversationSearchResult,
)
from app.schemas.message import MessageResponse
from app.services.conversation import (
    create_conversation,
    get_user_conversations,
    get_conversation,
    delete_conversation,
    rename_conversation,
    update_conversation_fields,
    search_conversations_service,
)

from app.crud.message import get_conversation_messages

router = APIRouter(
    prefix="/conversations",
    tags=["Conversations"],
)


@router.post("", response_model=ConversationResponse)
def create_new_conversation(
    conversation: ConversationCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return create_conversation(
        db=db,
        user_id=current_user.id,
        title=conversation.title,
    )


@router.get("", response_model=list[ConversationResponse])
def list_conversations(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return get_user_conversations(
        db=db,
        user_id=current_user.id,
    )


@router.get("/search", response_model=list[ConversationSearchResult])
def search_conversations(
    q: str = Query("", description="Search query string"),
    limit: int = Query(20, ge=1, le=100, description="Max conversations to return"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    clean_q = q.strip()
    if not clean_q:
        return []

    return search_conversations_service(
        db=db,
        user_id=current_user.id,
        query_str=clean_q,
        limit=limit,
    )


@router.get("/{conversation_id}")
def get_single_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    conversation = get_conversation(
        db,
        conversation_id,
    )

    if conversation is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        )

    if conversation.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Access denied",
        )

    return conversation


@router.get(
    "/{conversation_id}/messages",
    response_model=list[MessageResponse],
)
def get_messages(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    conversation = get_conversation(
        db,
        conversation_id,
    )

    if conversation is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        )

    if conversation.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Access denied",
        )

    return get_conversation_messages(
        db,
        conversation_id,
    )


@router.patch(
    "/{conversation_id}",
    response_model=ConversationResponse,
)
def rename_single_conversation(
    conversation_id: int,
    conversation_update: ConversationUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    conversation = get_conversation(
        db,
        conversation_id,
    )

    if conversation is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        )

    if conversation.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Access denied",
        )

    return update_conversation_fields(
        db=db,
        conversation=conversation,
        title=conversation_update.title,
        is_pinned=conversation_update.is_pinned,
    )


@router.delete("/{conversation_id}")
def remove_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    conversation = get_conversation(
        db,
        conversation_id,
    )

    if conversation is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        )

    if conversation.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Access denied",
        )

    delete_conversation(
        db,
        conversation,
    )

    return {
        "message": "Conversation deleted successfully",
    }
