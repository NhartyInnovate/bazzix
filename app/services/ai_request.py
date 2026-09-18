from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.ai_request import AIRequestLog, RequestStatus, UsageSource

class DuplicateRequestError(Exception):
    pass

def create_ai_request_log(
    db: Session,
    client_request_id: str,
    user_id: int,
    conversation_id: int,
    provider: str = "openai",
    model: str = "gpt-4.1-mini",
) -> AIRequestLog:
    """Creates a PENDING AI request log."""
    log = AIRequestLog(
        client_request_id=client_request_id,
        user_id=user_id,
        conversation_id=conversation_id,
        provider=provider,
        model=model,
        status=RequestStatus.PENDING,
    )
    db.add(log)
    try:
        db.commit()
        db.refresh(log)
        return log
    except IntegrityError:
        db.rollback()
        existing = db.query(AIRequestLog).filter_by(
            user_id=user_id, client_request_id=client_request_id
        ).first()
        state = existing.status.value if existing else "UNKNOWN"
        raise DuplicateRequestError(f"Duplicate request ID: {client_request_id} (State: {state})")


def get_ai_request_log_by_client_id(
    db: Session,
    user_id: int,
    client_request_id: str
) -> AIRequestLog:
    return db.query(AIRequestLog).filter(
        AIRequestLog.user_id == user_id,
        AIRequestLog.client_request_id == client_request_id
    ).first()


def finalize_ai_request_log(
    db: Session,
    log: AIRequestLog,
    provider_request_id: str = None,
    prompt_tokens: int = None,
    cached_tokens: int = None,
    completion_tokens: int = None,
    usage_source: UsageSource = None,
    status: RequestStatus = RequestStatus.COMPLETED,
):
    """Finalizes an AI request log with usage data and terminal status."""
    if provider_request_id:
        log.provider_request_id = provider_request_id
    
    if prompt_tokens is not None:
        log.prompt_tokens = prompt_tokens
        
    if cached_tokens is not None:
        log.cached_tokens = cached_tokens
    
    if completion_tokens is not None:
        log.completion_tokens = completion_tokens
        
    if usage_source:
        log.usage_source = usage_source
        
    log.status = status
    
    db.add(log)
    db.commit()
    db.refresh(log)
    return log
