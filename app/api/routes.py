from fastapi import APIRouter, Depends, HTTPException, Request, status
from app.core.config import Settings, get_settings
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.contact import ContactFormRequest, ContactFormResponse
from app.services.contact_service import (
    mark_email_sent,
    save_message_to_db,
    send_acknowledgement_email_async,
    send_smtp_email_async,
    verify_recaptcha,
)

router = APIRouter()

PREPARING_NOTICE = (
    "Подключение AI-ассистента подготавливается. В следующей версии он сможет отвечать "
    "на вопросы о профессиональном опыте, навыках, образовании и проектах Андриса Янчевскиса."
)


@router.get("/health", summary="Проверка состояния сервиса")
async def health_check(settings: Settings = Depends(get_settings)) -> dict:
    """Возвращает текущий статус сервиса и его наименование из настроек."""
    return {
        "status": "ok",
        "service": settings.app_name,
    }


@router.post(
    "/api/chat",
    response_model=ChatResponse,
    summary="Интерфейс обращения к AI-ассистенту",
)
async def chat_endpoint(request: ChatRequest) -> ChatResponse:
    """Честное уведомление о том, что AI-интеграция подготавливается."""
    return ChatResponse(
        reply=PREPARING_NOTICE,
        status="preparing",
    )


@router.post(
    "/api/contact",
    response_model=ContactFormResponse,
    summary="Отправка сообщения через контактную форму",
)
async def contact_form_endpoint(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> ContactFormResponse:
    """Прием контактной формы, валидация reCAPTCHA, сохранение в SQLite и отправка email через SMTP."""
    content_type = request.headers.get("content-type", "")
    try:
        if "application/json" in content_type:
            data = await request.json()
            payload = ContactFormRequest(**data)
        else:
            form = await request.form()
            payload = ContactFormRequest(
                name=str(form.get("name", "")),
                email=str(form.get("email", "")),
                subject=str(form.get("subject", "")) or None,
                message=str(form.get("message", "")),
                recaptcha_token=str(form.get("g-recaptcha-response") or form.get("recaptcha_token") or "") or None,
            )
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Ошибка валидации полей формы: {exc}",
        )

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", "")

    # 1. reCAPTCHA проверка
    is_recaptcha_valid = await verify_recaptcha(
        payload.recaptcha_token, client_ip, settings
    )
    if not is_recaptcha_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Проверка reCAPTCHA не пройдена. Пожалуйста, подтвердите, что вы не робот.",
        )

    # 2. Сохранение сообщения в SQLite базу данных (/data)
    message_id = save_message_to_db(
        name=payload.name,
        email_addr=payload.email,
        subject=payload.subject,
        message=payload.message,
        ip_address=client_ip,
        user_agent=user_agent,
        settings=settings,
    )

    # 3. Отправка уведомления администратору и подтверждения отправителю через SMTP (если настроено)
    email_sent = False
    acknowledgement_sent = False
    if settings.smtp_host:
        email_sent = await send_smtp_email_async(
            name=payload.name,
            email_addr=payload.email,
            subject=payload.subject,
            message=payload.message,
            settings=settings,
        )
        if email_sent:
            mark_email_sent(message_id, settings)

        acknowledgement_sent = await send_acknowledgement_email_async(
            name=payload.name,
            email_addr=payload.email,
            subject=payload.subject,
            message=payload.message,
            settings=settings,
        )

    ack_note = f" Подтверждение направлено на ваш адрес {payload.email}." if acknowledgement_sent else ""
    return ContactFormResponse(
        success=True,
        message=f"Спасибо, {payload.name}! Ваше сообщение успешно отправлено.{ack_note}",
        message_id=message_id,
        email_sent=email_sent,
        acknowledgement_sent=acknowledgement_sent,
    )

