import re
from typing import Optional
from pydantic import BaseModel, Field, field_validator

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


class ContactFormRequest(BaseModel):
    """Schema for contact form incoming payload."""

    name: str = Field(..., min_length=2, max_length=100, description="Имя отправителя")
    email: str = Field(..., min_length=5, max_length=255, description="Email для обратной связи")
    subject: str = Field(..., min_length=5, max_length=200, description="Тема сообщения")
    message: str = Field(..., min_length=5, max_length=5000, description="Текст сообщения")
    recaptcha_token: Optional[str] = Field(None, description="Токен Google reCAPTCHA")

    @field_validator("subject")
    @classmethod
    def validate_subject(cls, value: str) -> str:
        clean = value.strip()
        if len(clean) < 5:
            raise ValueError("Тема сообщения обязательна для заполнения (не менее 5 символов)")
        return clean

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, value: str) -> str:
        clean = value.strip()
        if not EMAIL_REGEX.match(clean):
            raise ValueError("Некорректный формат email адреса")
        return clean.lower()


class ContactFormResponse(BaseModel):
    """Schema for contact form response."""

    success: bool
    message: str
    message_id: Optional[int] = None
    email_sent: bool = False
    acknowledgement_sent: bool = False
