from fastapi import APIRouter, Depends
from app.core.config import Settings, get_settings
from app.schemas.chat import ChatRequest, ChatResponse

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
