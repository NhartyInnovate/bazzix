import re
from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.message import Message


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
        .order_by(Conversation.is_pinned.desc(), Conversation.updated_at.desc(), Conversation.id.desc())
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


def escape_like_pattern(text: str) -> str:
    """Escape %, _, and backslash for SQL LIKE/ILIKE patterns."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def extract_snippet(content: str, query: str, max_chars: int = 120) -> str:
    """Extracts a snippet around the matched search term."""
    if not content or not query:
        return ""

    match = re.search(re.escape(query), content, re.IGNORECASE)
    if not match:
        if len(content) <= max_chars:
            return content.replace("\n", " ").strip()
        return content[:max_chars].replace("\n", " ").strip() + "..."

    start_pos, end_pos = match.span()
    match_len = end_pos - start_pos

    remaining_space = max(0, max_chars - match_len)
    padding_before = remaining_space // 3
    padding_after = remaining_space - padding_before

    snippet_start = max(0, start_pos - padding_before)
    snippet_end = min(len(content), end_pos + padding_after)

    prefix = "..." if snippet_start > 0 else ""
    suffix = "..." if snippet_end < len(content) else ""

    snippet = content[snippet_start:snippet_end].replace("\n", " ").strip()
    return f"{prefix}{snippet}{suffix}"


def search_user_conversations(
    db: Session,
    user_id: int,
    query_str: str,
    limit: int = 20,
) -> list[dict]:
    """
    Search conversation titles and message contents owned by user_id.
    Returns deduplicated conversations with matching snippets, deterministically ordered:
    1. Pinned conversations first
    2. Direct title matches before content-only matches
    3. Most recently updated
    """
    clean_query = query_str.strip()
    if not clean_query:
        return []

    escaped = escape_like_pattern(clean_query)
    like_pattern = f"%{escaped}%"

    # 1. Query conversations where title matches
    title_matches = (
        db.query(Conversation)
        .filter(
            Conversation.user_id == user_id,
            Conversation.title.ilike(like_pattern, escape="\\"),
        )
        .all()
    )

    # 2. Query messages where content matches, strictly joined on user-owned conversations
    message_matches = (
        db.query(Message, Conversation)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(
            Conversation.user_id == user_id,
            Message.content.ilike(like_pattern, escape="\\"),
        )
        .order_by(Message.created_at.desc())
        .all()
    )

    # 3. Deduplicate by conversation ID
    results_by_conv_id: dict[int, dict] = {}

    for conv in title_matches:
        results_by_conv_id[conv.id] = {
            "id": conv.id,
            "title": conv.title,
            "is_pinned": conv.is_pinned,
            "created_at": conv.created_at,
            "updated_at": conv.updated_at,
            "matching_snippet": None,
            "_is_title_match": True,
        }

    for msg, conv in message_matches:
        snippet = extract_snippet(msg.content, clean_query)
        if conv.id in results_by_conv_id:
            if not results_by_conv_id[conv.id]["matching_snippet"]:
                results_by_conv_id[conv.id]["matching_snippet"] = snippet
        else:
            results_by_conv_id[conv.id] = {
                "id": conv.id,
                "title": conv.title,
                "is_pinned": conv.is_pinned,
                "created_at": conv.created_at,
                "updated_at": conv.updated_at,
                "matching_snippet": snippet,
                "_is_title_match": False,
            }

    # 4. Deterministic sorting: pinned first, title matches next, recency last
    sorted_results = sorted(
        results_by_conv_id.values(),
        key=lambda r: (
            1 if r["is_pinned"] else 0,
            1 if r["_is_title_match"] else 0,
            r["updated_at"] or r["created_at"],
        ),
        reverse=True,
    )

    final_results = sorted_results[:limit]
    for r in final_results:
        r.pop("_is_title_match", None)

    return final_results
