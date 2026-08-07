from pydantic import BaseModel, Field
from datetime import datetime


class ConversationCreate(BaseModel):
    title: str = Field("New Chat", min_length=1, max_length=100)


class ConversationUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=100)
    is_pinned: bool | None = None

    
class ConversationResponse(BaseModel):
    id: int
    title: str
    is_pinned: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True