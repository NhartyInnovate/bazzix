import base64
from datetime import datetime
from sqlalchemy import or_, and_
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


def encode_cursor(created_at: datetime, message_id: int) -> str:
    payload = f"{created_at.isoformat()}|{message_id}".encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def decode_cursor(cursor_str: str) -> tuple[datetime, int]:
    try:
        pad = cursor_str + "=" * (-len(cursor_str) % 4)
        raw = base64.urlsafe_b64decode(pad.encode("ascii")).decode("utf-8")
        ts_part, id_part = raw.rsplit("|", 1)
        created_at = datetime.fromisoformat(ts_part)
        message_id = int(id_part)
        return created_at, message_id
    except Exception as e:
        raise ValueError("Invalid pagination cursor") from e


def get_conversation_messages_paginated(
    db: Session,
    conversation_id: int,
    limit: int | None = None,
    cursor: str | None = None,
    before_id: int | None = None,
) -> tuple[list[Message], bool, str | None]:
    """
    Retrieve messages for a conversation with compound keyset pagination.

    If limit is None and no pagination anchors are provided:
        Returns all messages in chronological order (created_at ASC, id ASC).
        has_more is False, next_cursor is None.

    If limit is provided:
        Retrieves the bounded page of messages older than cursor/before_id
        (or the most recent messages if neither is provided).
        The returned list is ordered chronologically (created_at ASC, id ASC).
        has_more is True if older messages exist beyond this page.
        next_cursor is an opaque cursor pointing to the oldest message in this page.
    """
    if limit is None and cursor is None and before_id is None:
        messages = (
            db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc(), Message.id.asc())
            .all()
        )
        return messages, False, None

    cursor_ts: datetime | None = None
    cursor_id: int | None = None

    if cursor is not None:
        cursor_ts, cursor_id = decode_cursor(cursor)
    elif before_id is not None:
        anchor = (
            db.query(Message)
            .filter(
                Message.conversation_id == conversation_id,
                Message.id == before_id,
            )
            .first()
        )
        if anchor is None:
            raise ValueError("Message anchor not found")
        cursor_ts = anchor.created_at
        cursor_id = anchor.id

    effective_limit = limit if limit is not None else 50

    query = db.query(Message).filter(Message.conversation_id == conversation_id)

    if cursor_ts is not None and cursor_id is not None:
        query = query.filter(
            or_(
                Message.created_at < cursor_ts,
                and_(
                    Message.created_at == cursor_ts,
                    Message.id < cursor_id,
                ),
            )
        )

    rows = (
        query.order_by(Message.created_at.desc(), Message.id.desc())
        .limit(effective_limit + 1)
        .all()
    )

    has_more = len(rows) > effective_limit
    items = rows[:effective_limit]

    messages = list(reversed(items))

    next_cursor = None
    if has_more and messages:
        earliest = messages[0]
        if earliest.created_at is not None:
            next_cursor = encode_cursor(earliest.created_at, earliest.id)

    return messages, has_more, next_cursor


def get_conversation_messages(
    db: Session,
    conversation_id: int,
) -> list[Message]:
    messages, _, _ = get_conversation_messages_paginated(db, conversation_id)
    return messages
