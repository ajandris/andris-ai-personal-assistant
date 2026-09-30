from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.routes import router
from app.core.config import get_settings

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
MEDIA_DIR = BASE_DIR.parent / "media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR = BASE_DIR / "templates"

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Персональный сайт с AI-ассистентом для представления профессиональных компетенций Андриса Янчевскиса",
    version="0.3.0",
)

# Подключение статических файлов и медиа
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")

# Шаблонизатор Jinja2
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Отдача favicon.ico для браузеров."""
    return FileResponse(STATIC_DIR / "images" / "favicon.ico")


@app.get("/", summary="Главная страница")
async def index_page(request: Request):
    """Отображение главной страницы персонального сайта."""
    current_settings = get_settings()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"settings": current_settings, "active_page": "home"},
    )


@app.get("/experience", summary="Страница опыта работы")
async def experience_page(request: Request):
    """Отображение страницы практического опыта работы."""
    current_settings = get_settings()
    return templates.TemplateResponse(
        request=request,
        name="experience.html",
        context={"settings": current_settings, "active_page": "experience"},
    )


@app.get("/skills", summary="Страница навыков")
async def skills_page(request: Request):
    """Отображение страницы навыков и компетенций."""
    current_settings = get_settings()
    return templates.TemplateResponse(
        request=request,
        name="skills.html",
        context={"settings": current_settings, "active_page": "skills"},
    )


@app.get("/education", summary="Страница образования и обучения")
async def education_page(request: Request):
    """Отображение страницы образования, квалификаций и сертификаций."""
    current_settings = get_settings()
    return templates.TemplateResponse(
        request=request,
        name="education.html",
        context={"settings": current_settings, "active_page": "education"},
    )


@app.get("/portfolio", summary="Страница портфолио")
async def portfolio_page(request: Request):
    """Отображение страницы портфолио проектов."""
    current_settings = get_settings()
    return templates.TemplateResponse(
        request=request,
        name="portfolio.html",
        context={"settings": current_settings, "active_page": "portfolio"},
    )


@app.get("/ai-assistant", summary="Страница AI-ассистента")
async def ai_assistant_page(request: Request):
    """Отображение отдельной страницы AI-ассистента."""
    current_settings = get_settings()
    return templates.TemplateResponse(
        request=request,
        name="ai_assistant.html",
        context={"settings": current_settings, "active_page": "ai_assistant"},
    )


# Подключение маршрутов API и health
app.include_router(router)
