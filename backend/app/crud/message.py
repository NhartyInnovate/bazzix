from sqlalchemy.sql import func
from sqlalchemy.orm import Session
from app.models.message import Message
from app.models.conversation import Conversation


def save_message(
    db: Session,
    conversation_id: int,
    role: str,
    content: str,
):
    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
    )

    db.add(message)
    # Update parent conversation's updated_at for latest activity sorting
    db.query(Conversation).filter(Conversation.id == conversation_id).update({"updated_at": func.now()})
    db.commit()
    db.refresh(message)

    return message


def get_conversation_messages(
    db: Session,
    conversation_id: int,
):
    return (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .all()
    )