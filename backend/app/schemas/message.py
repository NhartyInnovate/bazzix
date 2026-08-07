from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    conversation_id: int
    message: str = Field(..., min_length=1, max_length=5000, description="Message content must be between 1 and 5000 characters.")


class ChatResponse(BaseModel):
    response: str


class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)