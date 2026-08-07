from sqlalchemy.orm import Session

from app.models.conversation import Conversation


def create_conversation(db: Session, user_id: int, title: str):
    conversation = Conversation(
        title=title,
        user_id=user_id,
    )

    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return conversation


def get_user_conversations(db: Session, user_id: int):
    return (
        db.query(Conversation)
        .filter(Conversation.user_id == user_id)
        .order_by(Conversation.is_pinned.desc(), Conversation.updated_at.desc())
        .all()
    )


def get_conversation(db: Session, conversation_id: int):
    return (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id)
        .first()
    )


def delete_conversation(db: Session, conversation):
    db.delete(conversation)
    db.commit()


def update_conversation_title(
    db: Session,
    conversation,
    title: str,
):
    conversation.title = title

    db.commit()

    print("Conversation title updated to:", conversation.title)

    db.refresh(conversation)

    return conversation


def update_conversation(
    db: Session,
    conversation,
    title: str | None = None,
    is_pinned: bool | None = None,
):
    if title is not None:
        conversation.title = title
    if is_pinned is not None:
        conversation.is_pinned = is_pinned

    db.commit()
    db.refresh(conversation)

    return conversation