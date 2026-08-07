from app.crud.conversation import (
    create_conversation,
    get_user_conversations,
    get_conversation,
    delete_conversation,
    update_conversation_title,
    update_conversation,
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