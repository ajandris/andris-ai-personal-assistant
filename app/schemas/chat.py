from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Schema for chat incoming request."""

    message: str = Field(..., min_length=1, description="Вопрос пользователя")


class ChatResponse(BaseModel):
    """Schema for chat response."""

    reply: str
    status: str = "preparing"
