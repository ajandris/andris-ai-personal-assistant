from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Single message in a multi-turn chat conversation."""

    role: str = Field(..., description="Role of the sender: 'user', 'assistant', or 'system'")
    content: str = Field(..., description="Message text")


class SourceItem(BaseModel):
    """Retrieved RAG source item."""

    title: str
    category: str
    source: str
    url: Optional[str] = None
    score: Optional[float] = None


class ChatRequest(BaseModel):
    """Schema for incoming chat message."""

    message: str = Field(..., min_length=1, description="Вопрос или описание требований пользователя")
    history: Optional[List[ChatMessage]] = Field(default=None, description="История предыдущих реплик диалога")
    contact_name: Optional[str] = Field(default=None, description="Имя посетителя (если передано напрямую)")
    contact_email: Optional[str] = Field(default=None, description="Email посетителя (если передан напрямую)")
    contact_phone: Optional[str] = Field(default=None, description="Телефон или Telegram посетителя")


class ChatResponse(BaseModel):
    """Schema for chat response."""

    reply: str
    status: str = "ok"
    sources: List[SourceItem] = []
    contact_captured: bool = False
    email_sent: bool = False


class LeadCaptureRequest(BaseModel):
    """Direct lead submission from chat widget."""

    name: str = Field(..., min_length=1, description="Имя посетителя")
    email: str = Field(..., min_length=3, description="Email или контакты для связи")
    phone: Optional[str] = Field(default=None, description="Телефон или Telegram")
    demands: Optional[str] = Field(default=None, description="Требования к вакансии или описание проекта")
    notes: Optional[str] = Field(default=None, description="Дополнительный комментарий")
    recaptcha_token: Optional[str] = Field(default=None, description="Google reCAPTCHA token")


class LeadCaptureResponse(BaseModel):
    """Response after capturing lead contact details."""

    success: bool
    message: str
    email_sent: bool = False
    message_id: Optional[int] = None
