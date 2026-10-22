from app.crud.conversation import (
    create_conversation,
    get_user_conversations,
    get_conversation,
    delete_conversation,
    update_conversation_title,
    update_conversation,
    search_user_conversations,
)


def rename_conversation(
    db,
    conversation,
    title: str,
):
    return update_conversation_title(
        db=db,
        conversation=conversation,
        title=title,
    )


def update_conversation_fields(
    db,
    conversation,
    title: str | None = None,
    is_pinned: bool | None = None,
):
    return update_conversation(
        db=db,
        conversation=conversation,
        title=title,
        is_pinned=is_pinned,
    )


def search_conversations_service(
    db,
    user_id: int,
    query_str: str,
    limit: int = 20,
):
    return search_user_conversations(
        db=db,
        user_id=user_id,
        query_str=query_str,
        limit=limit,
    )
